"""
app.py — AI Study Buddy · Pure UI logic
All styling is imported from config.py
"""
from __future__ import annotations
import os
import uuid
import json
import warnings
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

import streamlit as st

# ── Import config (sets page config, CSS, and constants) ──────────────────
from config import (
    local_css, MISTRAL_API_KEY, TAVILY_API_KEY,
    UPLOAD_DIR, MAX_RETRIES, QUIZ_PASS_SCORE
)

# ── Apply CSS ──────────────────────────────────────────────────────────────
local_css()

# ── Backend imports (agents, memory, utils) ──────────────────────────────
from agents.planner_agent import run_planner
from agents.researcher_agent import run_researcher
from agents.quiz_agent import generate_quiz, score_quiz
from agents.evaluator_agent import run_evaluator
from agents.chat_agent import run_chat
from memory.vector_store import (
    store_note, retrieve_notes, list_all_subtopics,
    get_note_count, clear_all, get_quiz_history, delete_document,
    store_quiz_result
)
from utils.file_extractor import extract_text, summarize_extracted

# ── Suppress warnings ──────────────────────────────────────────────────────
warnings.filterwarnings("ignore", message="Could not get FontBBox from font descriptor")

# ── Persistent state helpers ──────────────────────────────────────────────
STATE_FILE = Path("data/study_buddy_state.json")

def save_persistent_state():
    data = {
        "chats": st.session_state.chats,
        "chromadb_mock_store": st.session_state.chromadb_mock_store,
        "planner_history": st.session_state.planner_history,
        "research_history": st.session_state.research_history,
        "current_chat_id": st.session_state.current_chat_id,
    }
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_persistent_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

saved_state = load_persistent_state()

# ── Session state initialisation ──────────────────────────────────────────
if "current_view" not in st.session_state:
    st.session_state.current_view = "Dashboard"

if saved_state:
    st.session_state.chats = saved_state.get("chats", {})
    st.session_state.chromadb_mock_store = saved_state.get("chromadb_mock_store", [])
    st.session_state.planner_history = saved_state.get("planner_history", [])
    st.session_state.research_history = saved_state.get("research_history", [])
    st.session_state.current_chat_id = saved_state.get("current_chat_id", None)
else:
    st.session_state.chats = {}
    st.session_state.chromadb_mock_store = []
    st.session_state.planner_history = []
    st.session_state.research_history = []
    st.session_state.current_chat_id = None

if "quiz_state" not in st.session_state:
    st.session_state.quiz_state = {
        "active": False,
        "topic": "",
        "questions": [],
        "current_q": 0,
        "answers": {},
        "finished": False,
        "score": 0,
        "session_id": None,
        "prefill_context": "",   # additional notes from planner/researcher
        "prefill_topic": "",     # topic from planner/researcher
    }

if "planner_output" not in st.session_state:
    st.session_state.planner_output = ""
if "researcher_output" not in st.session_state:
    st.session_state.researcher_output = ""
if "show_upload" not in st.session_state:
    st.session_state.show_upload = {}

# ── Helper functions ────────────────────────────────────────────────────────
def delete_chat_callback(chat_id: str):
    if chat_id in st.session_state.chats:
        del st.session_state.chats[chat_id]
    if st.session_state.current_chat_id == chat_id:
        remaining = list(st.session_state.chats.keys())
        if remaining:
            st.session_state.current_chat_id = remaining[0]
        else:
            st.session_state.chats = {}
            st.session_state.current_chat_id = None
    conv_file = Path("data/conversations") / f"{chat_id}.json"
    if conv_file.exists():
        conv_file.unlink()
    save_persistent_state()

def new_chat_callback():
    new_id = str(uuid.uuid4())
    st.session_state.chats[new_id] = {
        "title": "New Chat Session",
        "timestamp": datetime.now().strftime("%I:%M %p"),
        "messages": [],
        "uploaded_files": [],
        "scanned_context": ""
    }
    st.session_state.current_chat_id = new_id
    st.session_state.current_view = "Chat with Buddy"
    save_persistent_state()

def handle_file_upload(uploaded_files, chat_id):
    chat = st.session_state.chats[chat_id]
    new_text = ""
    for uf in uploaded_files:
        chat["uploaded_files"].append({"name": uf.name, "type": uf.type, "size": uf.size})
        tmp_path = os.path.join(UPLOAD_DIR, uf.name)
        with open(tmp_path, "wb") as f:
            f.write(uf.read())
        try:
            raw_text = extract_text(tmp_path)
            summary = summarize_extracted(raw_text)
            store_note(subtopic=uf.name, content=summary, source="upload")
            new_text += f"\n\n--- Content from {uf.name} ---\n{summary}"
        except Exception as e:
            new_text += f"\n\n--- Error processing {uf.name}: {e} ---"
    chat["scanned_context"] += new_text
    save_persistent_state()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-branding">
            <div class="sb-logo-rect">SB</div>
            <div class="branding-text">
                <h2>Study Buddy</h2>
                <p>Local AI tutor</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.button("+ New Chat", on_click=new_chat_callback, key="new_chat", use_container_width=True)

    if st.session_state.chats:
        st.markdown("**Recent Chats**")
        for chat_id in reversed(list(st.session_state.chats.keys())[-10:]):
            chat = st.session_state.chats[chat_id]
            title = chat["title"]
            st.markdown('<div class="chat-row-container">', unsafe_allow_html=True)
            cols = st.columns([0.85, 0.15], gap="small")
            with cols[0]:
                st.markdown('<div class="chat-name-btn">', unsafe_allow_html=True)
                if st.button(f"💬 {title[:30]}{'...' if len(title)>30 else ''}",
                             key=f"chat_btn_{chat_id}", use_container_width=True):
                    st.session_state.current_chat_id = chat_id
                    st.session_state.current_view = "Chat with Buddy"
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                st.button("🗑️", key=f"del_{chat_id}", on_click=delete_chat_callback, args=(chat_id,))
                st.markdown('</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    nav_items = ["Dashboard", "Planner", "Researcher", "Quiz Agent", "Chat with Buddy", "History", "Settings"]
    for item in nav_items:
        if st.button(item, key=f"nav_{item}", use_container_width=True):
            if item == "Chat with Buddy" and not st.session_state.chats:
                new_chat_callback()
            else:
                st.session_state.current_view = item
                if item != "Quiz Agent":
                    st.session_state.quiz_state["active"] = False
                st.rerun()

    st.markdown("---")
    st.markdown(
        """
        <div class="user-profile-box">
            <p class="user-name">SAMBIT SEN</p>
            <p class="user-plan">Free Plan Demo</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ── Main View Router ──────────────────────────────────────────────────────
view = st.session_state.current_view

# ========== Dashboard =====================================================
if view == "Dashboard":
    st.markdown("""
    <div class="banner-card">
        <div class="banner-text">
            <h2>Your AI Study Partner</h2>
            <p>Plan, research, quiz, remember, and improve with a local multi-agent tutor.</p>
        </div>
        <div class="robot-avatar">
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2a2 2 0 0 1 2 2v1h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4V4a2 2 0 0 1 2-2zM8 9a1 1 0 0 0-1 1v4a1 1 0 0 0 2 0v-4a1 1 0 0 0-1-1zm8 0a1 1 0 0 0-1 1v4a1 1 0 0 0 2 0v-4a1 1 0 0 0-1-1zm-4 4a1 1 0 0 0-1 1v1a1 1 0 0 0 2 0v-1a1 1 0 0 0-1-1z"/>
                <circle cx="9" cy="15" r="1" fill="white"/>
                <circle cx="15" cy="15" r="1" fill="white"/>
            </svg>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("dash_search", clear_on_submit=True):
        search_col, btn_col = st.columns([4, 1])
        with search_col:
            search_query = st.text_input("Search", placeholder="Ask anything, like: Create a 5-day study plan on LangGraph", label_visibility="collapsed")
        with btn_col:
            submitted = st.form_submit_button("🔍")
        if submitted and search_query.strip():
            new_id = str(uuid.uuid4())
            st.session_state.chats[new_id] = {
                "title": "New Chat Session",
                "timestamp": datetime.now().strftime("%I:%M %p"),
                "messages": [],
                "uploaded_files": [],
                "scanned_context": ""
            }
            st.session_state.chats[new_id]["messages"].append({"role": "user", "content": search_query.strip()})
            first_words = " ".join(search_query.strip().split()[:4])
            st.session_state.chats[new_id]["title"] = first_words + ("..." if len(search_query.split()) > 4 else "")
            with st.spinner("Thinking..."):
                response = run_chat(search_query.strip(), history=[], document_context=st.session_state.chats[new_id].get("scanned_context", ""))
            st.session_state.chats[new_id]["messages"].append({"role": "assistant", "content": response})
            st.session_state.current_chat_id = new_id
            st.session_state.current_view = "Chat with Buddy"
            save_persistent_state()
            st.rerun()

    cols = st.columns(4)
    with cols[0]:
        if st.button("💬 Send to Buddy", type="primary", use_container_width=True):
            st.session_state.current_view = "Chat with Buddy"
            st.rerun()
    with cols[1]:
        if st.button("📋 Planner Agent", type="primary", use_container_width=True):
            st.session_state.current_view = "Planner"
            st.rerun()
    with cols[2]:
        if st.button("🔍 Researcher Agent", type="primary", use_container_width=True):
            st.session_state.current_view = "Researcher"
            st.rerun()
    with cols[3]:
        if st.button("❓ Quiz Agent", type="primary", use_container_width=True):
            st.session_state.current_view = "Quiz Agent"
            st.rerun()

    st.markdown("---")
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.markdown('<div class="dashboard-card-box"><h3>📋 Create Study Plan</h3><p>Generate a structured path with daily deliverables.</p></div>', unsafe_allow_html=True)
        if st.button("Go to Planner", key="quick_planner", type="primary"):
            st.session_state.current_view = "Planner"
            st.rerun()
    with row1_col2:
        st.markdown('<div class="dashboard-card-box"><h3>🔍 Research Topic</h3><p>Search or use curated notes to explain a subject.</p></div>', unsafe_allow_html=True)
        if st.button("Go to Researcher", key="quick_researcher", type="primary"):
            st.session_state.current_view = "Researcher"
            st.rerun()
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.markdown('<div class="dashboard-card-box"><h3>📝 Take a Quiz</h3><p>Test your knowledge and trigger review when needed.</p></div>', unsafe_allow_html=True)
        if st.button("Start Quiz", key="quick_quiz", type="primary"):
            st.session_state.current_view = "Quiz Agent"
            st.rerun()
    with row2_col2:
        st.markdown('<div class="dashboard-card-box"><h3>🧠 Review Memory</h3><p>Search saved notes from earlier sessions.</p></div>', unsafe_allow_html=True)
        if st.button("Open Memory", key="quick_memory", type="primary"):
            st.session_state.current_view = "History"
            st.rerun()

    st.markdown("---")
    st.subheader("Snapshot")
    total_history = (len(st.session_state.chats) + len(st.session_state.chromadb_mock_store) +
                     len(st.session_state.research_history) + len(st.session_state.planner_history) +
                     get_note_count())
    recent_score = "N/A"
    if st.session_state.chromadb_mock_store:
        last_quiz = st.session_state.chromadb_mock_store[-1]
        recent_score = f"{last_quiz['score']}%"
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.markdown(f"""
        <div class="dashboard-card-box snapshot-card">
            <p class="snapshot-number">{total_history}</p>
            <p class="snapshot-label">Total history saved</p>
        </div>
        """, unsafe_allow_html=True)
    with metric_col2:
        st.markdown(f"""
        <div class="dashboard-card-box snapshot-card">
            <p class="snapshot-number">{recent_score}</p>
            <p class="snapshot-label">Recent scores</p>
        </div>
        """, unsafe_allow_html=True)
    with metric_col3:
        st.markdown("""
        <div class="dashboard-card-box snapshot-card">
            <p class="snapshot-number">LangGraph</p>
            <p class="snapshot-label">Workflow engine</p>
        </div>
        """, unsafe_allow_html=True)

# ========== Planner ========================================================
# ========== Planner ========================================================
elif view == "Planner":
    st.markdown("""<div class="dashboard-card-box"><h1>📋 Planner Agent</h1><p>&nbsp;&nbsp;&nbsp;&nbsp;Generate a detailed, structured study plan.</p></div>""", unsafe_allow_html=True)

    # Single checkbox: include uploaded documents
    use_docs = st.checkbox("Include uploaded documents", value=True, key="planner_use_docs")

    topic = st.text_input("Topic", placeholder="LangGraph")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        days = st.number_input("Days", min_value=1, max_value=90, value=15, step=1)
    with col_b:
        minutes = st.slider("Minutes per day", 15, 120, 45)
    with col_c:
        difficulty = st.selectbox("Difficulty", ["Beginner Friendly", "Intermediate", "Advanced"])

    if st.button("Generate Study Plan", type="primary", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a topic")
        else:
            with st.spinner("Creating detailed plan..."):
                chat_id = st.session_state.current_chat_id
                doc_context = ""
                if chat_id and chat_id in st.session_state.chats:
                    doc_context = st.session_state.chats[chat_id].get("scanned_context", "")

                context = doc_context if use_docs else ""

                plan = run_planner(topic=topic.strip(), duration_days=int(days), context_notes=context)

                # Build detailed markdown
                plan_text = f"## 📚 Study Plan: {plan.get('topic', topic)}\n\n"
                plan_text += f"*{plan.get('overview', '')}*\n\n"
                for sub in plan.get("subtopics", []):
                    plan_text += f"### 📅 Day {sub.get('day')} — {sub.get('title')}\n\n"
                    # Description
                    if sub.get("description"):
                        plan_text += f"{sub['description']}\n\n"
                    # Objectives
                    if sub.get("objectives"):
                        plan_text += "**Learning Objectives:**\n"
                        for obj in sub["objectives"]:
                            plan_text += f"- {obj}\n"
                        plan_text += "\n"
                    # Key Concepts
                    if sub.get("key_concepts"):
                        plan_text += "**Key Concepts:**\n"
                        for kc in sub["key_concepts"]:
                            plan_text += f"- {kc}\n"
                        plan_text += "\n"
                    # Practice Tasks
                    if sub.get("practice"):
                        plan_text += "**Practice Tasks:**\n"
                        for task in sub["practice"]:
                            plan_text += f"- {task}\n"
                        plan_text += "\n"
                    # Resources
                    if sub.get("resources"):
                        plan_text += "**Resources:**\n"
                        for res in sub["resources"]:
                            plan_text += f"- {res}\n"
                        plan_text += "\n"
                    plan_text += "---\n\n"

                st.session_state.planner_output = plan_text
                st.session_state.planner_history.append({
                    "topic": topic,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "content": plan_text
                })
                save_persistent_state()
            st.markdown(plan_text)

    if st.session_state.planner_output:
        # Button to quiz on this topic
        if st.button("📝 Quiz on this topic", type="primary"):
            # Pre-fill quiz with topic and context (the plan text)
            st.session_state.quiz_state["prefill_topic"] = topic if topic.strip() else "General Study"
            st.session_state.quiz_state["prefill_context"] = st.session_state.planner_output
            st.session_state.current_view = "Quiz Agent"
            st.rerun()

# ========== Researcher ====================================================
elif view == "Researcher":
    st.markdown("""<div class="dashboard-card-box"><h1>🔬 Researcher Agent</h1><p>&nbsp;&nbsp;&nbsp;&nbsp;Researches a topic, summarizes notes, and keeps sources visible.</p></div>""", unsafe_allow_html=True)

    # Two checkboxes: web search and uploaded documents
    use_web = st.checkbox("Use web search (Mistral)", value=True, key="researcher_use_web")
    use_docs = st.checkbox("Use uploaded documents", value=True, key="researcher_use_docs")

    topic = st.text_input("Research topic", placeholder="LangGraph")
    focus = st.text_input("Focus", placeholder="Example: state machine, memory, tool use")

    if st.button("Run Researcher", type="primary", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a research topic")
        elif not use_web and not use_docs:
            st.warning("At least one source must be selected.")
        else:
            with st.spinner("Researching..."):
                chat_id = st.session_state.current_chat_id
                doc_context = ""
                history = []
                if chat_id and chat_id in st.session_state.chats:
                    doc_context = st.session_state.chats[chat_id].get("scanned_context", "")
                    history = st.session_state.chats[chat_id].get("messages", [])

                search_q = focus.strip() or topic.strip() if use_web else None
                context = doc_context if use_docs else ""

                notes = run_researcher(
                    subtopic=topic.strip(),
                    search_query=search_q,
                    document_context=context,
                    history=history
                )
                st.session_state.researcher_output = notes
                st.session_state.research_history.append({
                    "topic": topic,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "content": notes
                })
                save_persistent_state()
            st.markdown(notes)

    if st.session_state.researcher_output:
        # Button to quiz on this topic
        if st.button("📝 Quiz on this topic", type="primary"):
            # Pre-fill quiz with topic and context (the research notes)
            st.session_state.quiz_state["prefill_topic"] = topic if topic.strip() else "General Research"
            st.session_state.quiz_state["prefill_context"] = st.session_state.researcher_output
            st.session_state.current_view = "Quiz Agent"
            st.rerun()

# ========== Quiz Agent ====================================================
elif view == "Quiz Agent":
    st.markdown("""<div class="dashboard-card-box"><h1>📝 Quiz Agent</h1><p>&nbsp;&nbsp;&nbsp;&nbsp;Creates MCQs, scores them, and re‑routes weak topics to Researcher Agent.</p></div>""", unsafe_allow_html=True)
    qs = st.session_state.quiz_state

    if not qs["active"]:
        # Checkbox: include uploaded documents
        use_docs = st.checkbox("Include uploaded documents", value=True, key="quiz_use_docs")

        col1, col2 = st.columns(2)
        with col1:
            # Pre-fill topic if coming from planner/researcher
            default_topic = qs.get("prefill_topic", "")
            topic = st.text_input("Quiz topic", placeholder="LangGraph", value=default_topic, key="quiz_topic")
        with col2:
            num_q = st.number_input("Questions", min_value=3, max_value=10, value=5, step=1, key="quiz_num")

        if st.button("Start Quiz", type="primary", use_container_width=True):
            if not topic.strip():
                st.warning("Please enter a topic")
            else:
                with st.spinner("Generating quiz questions via Mistral..."):
                    notes = ""
                    # Retrieve notes from vector store if using docs
                    if use_docs:
                        hits = retrieve_notes(topic, n_results=3)
                        if hits:
                            notes = "\n\n".join(h["content"] for h in hits)

                    # Also include prefill context from planner/researcher if available
                    prefill_context = qs.get("prefill_context", "")
                    if prefill_context:
                        notes += f"\n\n--- Additional context from planner/researcher ---\n{prefill_context}"

                    # If no notes, pass a generic prompt
                    quiz_data = generate_quiz(
                        notes or f"Generate a quiz about {topic}",
                        subtopic=topic,
                        num_questions=int(num_q)
                    )
                    if "questions" not in quiz_data:
                        st.error("Failed to generate quiz. Please try again.")
                        st.stop()
                    qs["questions"] = quiz_data["questions"]
                    qs["active"] = True
                    qs["current_q"] = 0
                    qs["answers"] = {}
                    qs["finished"] = False
                    qs["score"] = 0
                    qs["session_id"] = str(uuid.uuid4())
                    qs["topic"] = topic
                    # Clear prefill data after use
                    qs["prefill_topic"] = ""
                    qs["prefill_context"] = ""
                    st.rerun()
    else:
        current_idx = qs["current_q"]
        total = len(qs["questions"])

        if not qs["finished"]:
            q = qs["questions"][current_idx]
            st.markdown(f"### Question {current_idx + 1} of {total}")
            st.markdown(f"**{q['question']}**")
            options = q.get("options", {})
            option_items = list(options.items())
            choice = st.radio(
                "Select your answer:",
                options=[f"{k}) {v}" for k, v in option_items],
                key=f"quiz_opt_{current_idx}",
                index=None,
                format_func=lambda x: x
            )
            selected_letter = None
            if choice:
                selected_letter = choice.split(")")[0]

            col1, col2, _ = st.columns([2, 2, 6])
            with col1:
                if current_idx > 0 and st.button("⬅ Previous"):
                    qs["current_q"] -= 1
                    st.rerun()
            with col2:
                if st.button("Submit Answer / Next ➡"):
                    if selected_letter:
                        qs["answers"][current_idx] = selected_letter
                        if current_idx < total - 1:
                            qs["current_q"] += 1
                            st.rerun()
                        else:
                            correct_cnt = sum(1 for i, ans in qs["answers"].items() if ans == qs["questions"][i]["answer"])
                            qs["score"] = int((correct_cnt / total) * 100)
                            qs["finished"] = True
                            st.session_state.chromadb_mock_store.append({
                                "topic": qs["topic"],
                                "score": qs["score"],
                                "total_questions": total,
                                "correct": correct_cnt,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "questions": qs["questions"],
                                "user_answers": {str(k): v for k, v in qs["answers"].items()},
                                "session_id": qs.get("session_id", "")
                            })
                            store_quiz_result(
                                topic=qs["topic"],
                                score=qs["score"]/100,
                                passed=qs["score"] >= 60,
                                retries=0,
                                metadata={"session_id": qs.get("session_id", "")}
                            )
                            save_persistent_state()
                            st.rerun()
                    else:
                        st.warning("Please select an answer.")
        else:
            score = qs["score"]
            st.markdown("## 🎯 Quiz Completed!")
            st.metric("Your Score", f"{score}%")
            if score >= 60:
                st.success("Great job! You passed.")
            else:
                st.error("Score under 60%. Automatically routing weak concepts back to the Researcher Agent.")
                if st.button("📚 Generate Deeper Notes Now", type="primary"):
                    with st.spinner("Re‑researching weak topics..."):
                        notes = run_researcher(
                            subtopic=qs["topic"],
                            search_query=f"{qs['topic']} explained in detail with examples",
                            document_context="",
                            history=[]
                        )
                        st.session_state.researcher_output = notes
                        st.session_state.current_view = "Researcher"
                        qs["active"] = False
                    st.rerun()

            with st.expander("ChromaDB Quiz History Records"):
                if st.session_state.chromadb_mock_store:
                    for i, record in enumerate(st.session_state.chromadb_mock_store):
                        st.markdown(f"**Record {i+1}** – {record['timestamp']}")
                        st.write(f"Topic: {record['topic']} | Score: {record['score']}% | {record['correct']}/{record['total_questions']}")
                else:
                    st.info("No quiz history yet.")

            if st.button("🔄 Take Another Quiz"):
                qs["active"] = False
                qs["finished"] = False
                st.rerun()

# ========== Chat with Buddy ================================================
elif view == "Chat with Buddy":
    st.markdown("## 💬 Chat with Buddy")
    if st.session_state.current_chat_id is None or st.session_state.current_chat_id not in st.session_state.chats:
        new_chat_callback()
        st.rerun()

    chat_id = st.session_state.current_chat_id
    chat = st.session_state.chats[chat_id]
    messages = chat["messages"]

    st.markdown('<div class="info-callout">💡 <strong>Tip:</strong> Upload PDFs, images, or text to ground your conversation.</div>', unsafe_allow_html=True)

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    upload_key = f"show_upload_{chat_id}"
    if upload_key not in st.session_state.show_upload:
        st.session_state.show_upload[upload_key] = False

    cols_attach = st.columns([0.07, 0.93], gap="small")
    with cols_attach[0]:
        if st.button("➕", key=f"attach_btn_{chat_id}"):
            st.session_state.show_upload[upload_key] = not st.session_state.show_upload[upload_key]
            st.rerun()

    if st.session_state.show_upload[upload_key]:
        uploaded_files = st.file_uploader(
            "Choose files",
            type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key=f"upload_{chat_id}"
        )
        if uploaded_files:
            with st.spinner("Scanning documents..."):
                handle_file_upload(uploaded_files, chat_id)
            st.success("🔍 Multi-modal document scanned and parsed into local context successfully.")
            st.session_state.show_upload[upload_key] = False
            save_persistent_state()
            st.rerun()

    if st.button("🧹 Clear current chat", key="clear_chat"):
        chat["messages"] = []
        chat["scanned_context"] = ""
        conv_file = Path("data/conversations") / f"{chat_id}.json"
        if conv_file.exists():
            conv_file.unlink()
        save_persistent_state()
        st.rerun()

    prompt = st.chat_input("Ask anything...", key=f"chat_input_{chat_id}")
    if prompt:
        chat["messages"].append({"role": "user", "content": prompt})
        if chat["title"] == "New Chat Session":
            first_words = " ".join(prompt.strip().split()[:4])
            chat["title"] = first_words + ("..." if len(prompt.split()) > 4 else "")
        context = chat.get("scanned_context", "")
        with st.spinner("Thinking..."):
            response = run_chat(prompt, history=chat["messages"][:-1], document_context=context)
        chat["messages"].append({"role": "assistant", "content": response})
        save_persistent_state()
        st.rerun()

# ========== History ========================================================
elif view == "History":
    st.title("📜 Activity History")
    st.caption("Review all your past activities.")

    def delete_chat_from_history(chat_id: str):
        if chat_id in st.session_state.chats:
            del st.session_state.chats[chat_id]
        if st.session_state.current_chat_id == chat_id:
            remaining = list(st.session_state.chats.keys())
            if remaining:
                st.session_state.current_chat_id = remaining[0]
            else:
                st.session_state.chats = {}
                st.session_state.current_chat_id = None
        conv_file = Path("data/conversations") / f"{chat_id}.json"
        if conv_file.exists():
            conv_file.unlink()
        save_persistent_state()

    def delete_quiz(index: int):
        if 0 <= index < len(st.session_state.chromadb_mock_store):
            record = st.session_state.chromadb_mock_store[index]
            session_id = record.get("session_id", "")
            if session_id:
                quiz_file = Path("data/quiz_history") / f"{session_id}.json"
                if quiz_file.exists():
                    quiz_file.unlink()
            del st.session_state.chromadb_mock_store[index]
            save_persistent_state()

    def delete_research(index: int):
        if 0 <= index < len(st.session_state.research_history):
            del st.session_state.research_history[index]
            save_persistent_state()

    def delete_planner(index: int):
        if 0 <= index < len(st.session_state.planner_history):
            del st.session_state.planner_history[index]
            save_persistent_state()

    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat History", "📝 Quiz History", "🔬 Research History", "📋 Planner History"])

    with tab1:
        st.subheader("Chat Sessions")
        if st.session_state.chats:
            for chat_id, chat_data in st.session_state.chats.items():
                with st.container():
                    cols = st.columns([0.85, 0.15])
                    with cols[0]:
                        with st.expander(f"Chat: {chat_data['title']} ({len(chat_data['messages'])} messages)"):
                            st.write(f"**Created:** {chat_data['timestamp']}")
                            if chat_data["messages"]:
                                first_msg = chat_data["messages"][0]["content"][:100]
                                st.write(f"**First message:** {first_msg}...")
                            if st.button("Open this chat", key=f"hist_open_{chat_id}"):
                                st.session_state.current_chat_id = chat_id
                                st.session_state.current_view = "Chat with Buddy"
                                st.rerun()
                    with cols[1]:
                        with st.popover("⋮"):
                            if st.button("🗑️ Delete", key=f"del_chat_hist_{chat_id}"):
                                st.session_state[f"flag_del_chat_{chat_id}"] = True
                    if st.session_state.get(f"flag_del_chat_{chat_id}"):
                        delete_chat_from_history(chat_id)
                        del st.session_state[f"flag_del_chat_{chat_id}"]
                        st.rerun()
        else:
            st.info("No chat sessions yet.")

    with tab2:
        st.subheader("Quiz History")
        if st.session_state.chromadb_mock_store:
            for idx in reversed(range(len(st.session_state.chromadb_mock_store))):
                record = st.session_state.chromadb_mock_store[idx]
                with st.container():
                    cols = st.columns([0.85, 0.15])
                    with cols[0]:
                        with st.expander(f"Quiz {idx+1}: {record['topic']} — {record['score']}%"):
                            st.write(f"**Taken at:** {record['timestamp']}")
                            st.write(f"**Score:** {record['score']}% ({record['correct']}/{record['total_questions']})")
                            if st.checkbox("Show detailed answers", key=f"hist_quiz_detail_{idx}"):
                                for q_idx, q in enumerate(record["questions"]):
                                    user_ans = record["user_answers"].get(str(q_idx), "No answer")
                                    correct_ans = q["answer"]
                                    user_text = q["options"].get(user_ans, "Unknown") if user_ans != "No answer" else "No answer"
                                    correct_text = q["options"].get(correct_ans, "Unknown")
                                    st.markdown(f"- **Q{q_idx+1}:** {q['question']}")
                                    st.write(f"  Your answer: **{user_ans}) {user_text}** | Correct: **{correct_ans}) {correct_text}** {'✅' if user_ans == correct_ans else '❌'}")
                    with cols[1]:
                        with st.popover("⋮"):
                            if st.button("🗑️ Delete", key=f"del_quiz_{idx}"):
                                st.session_state[f"flag_del_quiz_{idx}"] = True
                    if st.session_state.get(f"flag_del_quiz_{idx}"):
                        delete_quiz(idx)
                        del st.session_state[f"flag_del_quiz_{idx}"]
                        st.rerun()
        else:
            st.info("No quiz history yet.")

    with tab3:
        st.subheader("Research History")
        if st.session_state.research_history:
            for idx in reversed(range(len(st.session_state.research_history))):
                entry = st.session_state.research_history[idx]
                with st.container():
                    cols = st.columns([0.85, 0.15])
                    with cols[0]:
                        with st.expander(f"Research {idx+1}: {entry['topic']} ({entry['timestamp']})"):
                            st.markdown(entry["content"])
                    with cols[1]:
                        with st.popover("⋮"):
                            if st.button("🗑️ Delete", key=f"del_research_{idx}"):
                                st.session_state[f"flag_del_research_{idx}"] = True
                    if st.session_state.get(f"flag_del_research_{idx}"):
                        delete_research(idx)
                        del st.session_state[f"flag_del_research_{idx}"]
                        st.rerun()
        else:
            st.info("No research history yet.")

    with tab4:
        st.subheader("Planner History")
        if st.session_state.planner_history:
            for idx in reversed(range(len(st.session_state.planner_history))):
                entry = st.session_state.planner_history[idx]
                with st.container():
                    cols = st.columns([0.85, 0.15])
                    with cols[0]:
                        with st.expander(f"Plan {idx+1}: {entry['topic']} ({entry['timestamp']})"):
                            st.markdown(entry["content"])
                    with cols[1]:
                        with st.popover("⋮"):
                            if st.button("🗑️ Delete", key=f"del_planner_{idx}"):
                                st.session_state[f"flag_del_planner_{idx}"] = True
                    if st.session_state.get(f"flag_del_planner_{idx}"):
                        delete_planner(idx)
                        del st.session_state[f"flag_del_planner_{idx}"]
                        st.rerun()
        else:
            st.info("No planner history yet.")

# ========== Settings ======================================================
elif view == "Settings":
    st.title("⚙️ Settings")
    st.write("Configure your Study Buddy preferences.")
    st.selectbox("Default model", ["Mistral 7B", "Llama 3"], index=0)
    if st.button("🗑️ Wipe all persistent data (cannot be undone)", type="primary"):
        clear_all()
        import shutil
        shutil.rmtree("data", ignore_errors=True)
        st.session_state.chats = {}
        st.session_state.chromadb_mock_store = []
        st.session_state.planner_history = []
        st.session_state.research_history = []
        st.session_state.current_chat_id = None
        st.session_state.planner_output = ""
        st.session_state.researcher_output = ""
        st.session_state.quiz_state = {
            "active": False,
            "topic": "",
            "questions": [],
            "current_q": 0,
            "answers": {},
            "finished": False,
            "score": 0,
            "session_id": None,
            "prefill_context": "",
            "prefill_topic": "",
        }
        save_persistent_state()
        st.success("All data wiped. Please refresh.")
        st.rerun()

# ── Footer ──────────────────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.caption("v1.0.0 · Local mode · Mistral + LangGraph")