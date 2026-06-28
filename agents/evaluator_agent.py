"""
agents/evaluator_agent.py — Scores quiz results and triggers re-study if score < 60%
"""
from __future__ import annotations
from config import QUIZ_PASS_SCORE, MAX_RETRIES
from agents.quiz_agent import score_quiz
from agents.researcher_agent import run_researcher
from memory.vector_store import retrieve_notes, store_quiz_result
from utils.llm_client import chat

FEEDBACK_SYSTEM = """You are a supportive academic coach.
Given a student's quiz performance, write 3–5 sentences of personalised feedback:
- Acknowledge what they got right
- Gently point out weak areas
- Give a specific study tip
Keep it encouraging and constructive."""

def run_evaluator(
    subtopic: str,
    questions: list[dict],
    student_answers: dict[int, str],
    retry_count: int = 0,
) -> dict:
    """
    Evaluate answers. If score < QUIZ_PASS_SCORE and retries remain,
    trigger re-research and return updated notes + flag.

    Returns:
    {
        "score_result":   <score dict>,
        "passed":         bool,
        "retry_triggered": bool,
        "new_notes":      str | None,
        "coach_feedback": str,
        "retry_count":    int,
    }
    """
    score_result = score_quiz(questions, student_answers)
    score = score_result.get("score", 0.0)
    passed = score >= QUIZ_PASS_SCORE

    # Store quiz result in memory for history
    store_quiz_result(subtopic, score, passed, retry_count)

    # Generate personalised coach feedback
    perf_text = (
        f"Subtopic: {subtopic}\n"
        f"Score: {score_result.get('correct_count', 0)}/{score_result.get('total', 5)} "
        f"({score * 100:.0f}%)\n"
        f"Feedback items: {score_result.get('feedback', [])}"
    )
    coach_feedback = chat(
        messages=[{"role": "user", "content": perf_text}],
        system=FEEDBACK_SYSTEM,
        temperature=0.7,
        max_tokens=300,
    )

    new_notes = None
    retry_triggered = False

    if not passed and retry_count < MAX_RETRIES:
        # Retrieve existing notes to supplement
        existing = retrieve_notes(subtopic, n_results=2)
        doc_ctx = "\n\n".join(n["content"] for n in existing)

        weak_ids = [
            f["question_id"]
            for f in score_result.get("feedback", [])
            if not f.get("correct")
        ]
        weak_hint = f"Focus especially on question IDs {weak_ids} — these were answered incorrectly."
        new_notes = run_researcher(
            subtopic=subtopic,
            search_query=f"{subtopic} explained in detail",
            document_context=doc_ctx + "\n" + weak_hint,
        )
        retry_triggered = True

    return {
        "score_result": score_result,
        "passed": passed,
        "retry_triggered": retry_triggered,
        "new_notes": new_notes,
        "coach_feedback": coach_feedback,
        "retry_count": retry_count,
    }