"""
graph.py — LangGraph StateGraph orchestrating all Study Buddy agents
with enterprise‑grade security guardrails for tool calls.

Graph topology:
  START
    └─► planner
          └─► researcher  (loops over subtopics)
                └─► quiz
                      └─► evaluator
                            ├─[pass]─► END
                            └─[fail, retries left]─► researcher (re-study)
"""
from __future__ import annotations
from typing import TypedDict, Annotated, List, Literal
import operator

from langgraph.graph import StateGraph, START, END

from agents.planner_agent import run_planner
from agents.researcher_agent import run_researcher
from agents.quiz_agent import generate_quiz
from agents.evaluator_agent import run_evaluator
from config import MAX_RETRIES, QUIZ_PASS_SCORE

# ── Import Guardrails ──────────────────────────────────────────────────────
from utils.guardrails import enforce_tool_schema

# ── Shared state schema ────────────────────────────────────────────────────
class StudyState(TypedDict):
    # Inputs
    topic: str
    duration_days: int
    document_context: str          # text extracted from uploaded files
    # Planner outputs
    study_plan: dict
    subtopics: list[dict]
    current_index: int
    # Researcher outputs
    current_notes: str
    all_notes: Annotated[list[str], operator.add]
    # Quiz / Eval
    current_quiz: dict
    student_answers: dict          # {question_id: letter}
    eval_result: dict
    retry_count: int
    # Chat history (short-term memory)
    chat_history: list[dict]
    # Output / status
    status_log: Annotated[list[str], operator.add]

# ── Node implementations ──────────────────────────────────────────────────
def node_planner(state: StudyState) -> dict:
    plan = run_planner(
        topic=state["topic"],
        duration_days=state["duration_days"],
        context_notes=state.get("document_context", ""),
    )
    return {
        "study_plan": plan,
        "subtopics": plan.get("subtopics", []),
        "current_index": 0,
        "status_log": [f"✅ Plan created: {len(plan.get('subtopics', []))} subtopics"],
    }

def node_researcher(state: StudyState) -> dict:
    idx = state.get("current_index", 0)
    subtopics = state.get("subtopics", [])
    if idx >= len(subtopics):
        return {"status_log": ["⚠️ No more subtopics to research"]}

    sub = subtopics[idx]
    title = sub.get("title", f"Subtopic {idx+1}")
    query = sub.get("resources", [title])[0] if sub.get("resources") else title

    # ─── GUARD: Enforce schema for the researcher tool ──────────────────
    params = {
        "subtopic": title,
        "search_query": query,
        "document_context": state.get("document_context", ""),
        "history": state.get("chat_history", []),
    }
    # This will raise ValueError if any parameter is invalid.
    safe_params = enforce_tool_schema("researcher", params)

    # Now call the researcher with validated parameters
    notes = run_researcher(
        subtopic=safe_params["subtopic"],
        search_query=safe_params["search_query"],
        document_context=safe_params["document_context"],
        history=safe_params["history"],
    )

    # `run_researcher` returns a dict with "text" and "doc_id"
    return {
        "current_notes": notes.get("text", notes) if isinstance(notes, dict) else notes,
        "all_notes": [notes.get("text", notes) if isinstance(notes, dict) else notes],
        "status_log": [f"📚 Researched: {title}"],
        "retry_count": 0,
    }

def node_quiz(state: StudyState) -> dict:
    idx = state.get("current_index", 0)
    subs = state.get("subtopics", [])
    title = subs[idx].get("title", "this topic") if idx < len(subs) else "this topic"
    notes = state.get("current_notes", "")
    quiz = generate_quiz(notes, subtopic=title)
    return {
        "current_quiz": quiz,
        "status_log": [f"❓ Quiz generated for: {title}"],
    }

def node_evaluator(state: StudyState) -> dict:
    questions = state.get("current_quiz", {}).get("questions", [])
    answers = state.get("student_answers", {})
    idx = state.get("current_index", 0)
    subs = state.get("subtopics", [])
    title = subs[idx].get("title", "this topic") if idx < len(subs) else "this topic"
    retry = state.get("retry_count", 0)

    result = run_evaluator(
        subtopic=title,
        questions=questions,
        student_answers=answers,
        retry_count=retry,
    )
    score_pct = result["score_result"].get("score", 0) * 100
    return {
        "eval_result": result,
        "retry_count": retry + (1 if result["retry_triggered"] else 0),
        "status_log": [f"📊 Score: {score_pct:.0f}% {'✅ PASSED' if result['passed'] else '🔄 Re-study triggered'}"],
    }

def node_advance(state: StudyState) -> dict:
    """Move to next subtopic."""
    return {
        "current_index": state.get("current_index", 0) + 1,
        "retry_count": 0,
        "status_log": ["➡️ Moving to next subtopic"],
    }

# ── Routing functions ──────────────────────────────────────────────────────
def route_after_eval(state: StudyState) -> Literal["researcher", "advance", "__end__"]:
    result = state.get("eval_result", {})
    passed = result.get("passed", True)
    retries = state.get("retry_count", 0)
    idx = state.get("current_index", 0)
    total = len(state.get("subtopics", []))

    if not passed and retries <= MAX_RETRIES:
        return "researcher"     # re-study

    if idx + 1 < total:
        return "advance"
    return END

def route_after_advance(state: StudyState) -> Literal["researcher", "__end__"]:
    idx = state.get("current_index", 0)
    total = len(state.get("subtopics", []))
    return "researcher" if idx < total else END

# ── Build graph ────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    g = StateGraph(StudyState)

    g.add_node("planner", node_planner)
    g.add_node("researcher", node_researcher)
    g.add_node("quiz", node_quiz)
    g.add_node("evaluator", node_evaluator)
    g.add_node("advance", node_advance)

    g.add_edge(START, "planner")
    g.add_edge("planner", "researcher")
    g.add_edge("researcher", "quiz")
    g.add_edge("quiz", "evaluator")

    g.add_conditional_edges("evaluator", route_after_eval, {
        "researcher": "researcher",
        "advance": "advance",
        END: END,
    })
    g.add_conditional_edges("advance", route_after_advance, {
        "researcher": "researcher",
        END: END,
    })

    return g.compile()

# Compiled singleton
study_graph = build_graph()