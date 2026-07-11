"""
app.py — AI Study Buddy · Complete UI with file & memory cleanup
"""
from __future__ import annotations
import os
import uuid
import json
import warnings
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

import streamlit as st

# ── Import config ──────────────────────────────────────────────────────────
from config import (
    local_css, MISTRAL_API_KEY, TAVILY_API_KEY,
    UPLOAD_DIR, MAX_RETRIES, QUIZ_PASS_SCORE
)

# ── Apply CSS ──────────────────────────────────────────────────────────────
local_css()

# ── Backend imports ──────────────────────────────────────────────────────
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
from utils.pdf_generator import markdown_to_pdf

# ── Suppress warnings ──────────────────────────────────────────────────────
warnings.filterwarnings("ignore", message="Could not get FontBBox from font descriptor")

# ── API key warning ──────────────────────────────────────────────────────
if not MISTRAL_API_KEY:
    st.warning("⚠️ MISTRAL_API_KEY is not set. The chat and agents will not work. Please add it to your .env file.")

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
        except Exception:
            return None
    return None

saved_state = load_persistent_state()

def build_clean_history(messages: list) -> list:
    """
    Return only user-assistant pairs where an assistant actually replied.
    This drops any orphaned user message that was blocked by guardrails.
    """
    clean = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg["role"] == "user":
            # If the very next message is an assistant reply, keep the pair
            if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                clean.append(msg)
                clean.append(messages[i + 1])
                i += 2
            else:
                # Orphaned user message (blocked) – skip it
                i += 1
        else:
            # Shouldn't normally happen; just move on
            i += 1
    return clean

# ── Session state initialisation ──────────────────────────────────────────
if "current_view" not in st.session_state:
    st.session_state.current_view = "Dashboard"

if "_state_loaded" not in st.session_state:
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
    st.session_state._state_loaded = True

if st.session_state.current_chat_id not in st.session_state.chats:
    if st.session_state.chats:
        st.session_state.current_chat_id = list(st.session_state.chats.keys())[-1]
    else:
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
        "prefill_context": "",
        "prefill_topic": "",
    }

if "planner_output" not in st.session_state:
    st.session_state.planner_output = ""
if "researcher_output" not in st.session_state:
    st.session_state.researcher_output = ""
if "show_upload" not in st.session_state:
    st.session_state.show_upload = {}
if "guard_error_message" not in st.session_state:
    st.session_state.guard_error_message = None

# ── Helper functions ──────────────────────────────────────────────────────
def delete_uploaded_files(chat_id: str):
    if chat_id in st.session_state.chats:
        chat = st.session_state.chats[chat_id]
        for file_info in chat.get("uploaded_files", []):
            file_path = os.path.join(UPLOAD_DIR, file_info["name"])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            doc_id = file_info.get("doc_id")
            if doc_id:
                try:
                    delete_document(doc_id)
                except Exception:
                    pass
        chat["uploaded_files"] = []
        chat["scanned_context"] = ""

def delete_chat_callback(chat_id: str):
    delete_uploaded_files(chat_id)
    if chat_id in st.session_state.chats:
        del st.session_state.chats[chat_id]
    if st.session_state.current_chat_id == chat_id:
        remaining = list(st.session_state.chats.keys())
        st.session_state.current_chat_id = remaining[-1] if remaining else None
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

def open_chat_callback(chat_id: str):
    if chat_id in st.session_state.chats:
        st.session_state.current_chat_id = chat_id
        st.session_state.current_view = "Chat with Buddy"
        save_persistent_state()

def handle_file_upload(uploaded_files, chat_id):
    chat = st.session_state.chats[chat_id]
    new_text = ""
    for uf in uploaded_files:
        tmp_path = os.path.join(UPLOAD_DIR, uf.name)
        with open(tmp_path, "wb") as f:
            f.write(uf.read())
        try:
            raw_text = extract_text(tmp_path)
            summary = summarize_extracted(raw_text)
            doc_id = store_note(subtopic=uf.name, content=summary, source="upload")
            chat["uploaded_files"].append({
                "name": uf.name,
                "type": uf.type,
                "size": uf.size,
                "doc_id": doc_id
            })
            new_text += f"\n\n--- Content from {uf.name} ---\n{summary}"
        except Exception as e:
            new_text += f"\n\n--- Error processing {uf.name}: {e} ---"
    chat["scanned_context"] += new_text
    save_persistent_state()
    return new_text

def build_chat_export(chat_id: str) -> str:
    chat = st.session_state.chats.get(chat_id, {})
    export = {
        "chat_id": chat_id,
        "title": chat.get("title", "Untitled"),
        "created": chat.get("timestamp", ""),
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message_count": len(chat.get("messages", [])),
        "messages": chat.get("messages", []),
        "uploaded_files": [f["name"] for f in chat.get("uploaded_files", [])],
    }
    return json.dumps(export, indent=2, ensure_ascii=False)

def build_full_export() -> str:
    export = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chats": st.session_state.chats,
        "quiz_history": st.session_state.chromadb_mock_store,
        "research_history": st.session_state.research_history,
        "planner_history": st.session_state.planner_history,
    }
    return json.dumps(export, indent=2, ensure_ascii=False)

def chat_to_pdf(chat_id: str) -> bytes:
    """Convert a chat conversation to PDF."""
    chat = st.session_state.chats.get(chat_id, {})
    title = chat.get("title", "Chat Conversation")
    created = chat.get("timestamp", "")
    messages = chat.get("messages", [])
    md = f"# {title}\n\n"
    if created:
        md += f"*Created: {created}*\n\n"
    md += f"**Total messages:** {len(messages)}\n\n---\n\n"
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        emoji = "🧑" if role == "user" else "🤖"
        md += f"**{emoji} {role.capitalize()}:**\n{content}\n\n"
    md += "\n---\n\n*Exported from Study Buddy AI*"
    return markdown_to_pdf(md, title=title)

# ── Security exception helper ─────────────────────────────────────────────
def handle_agent_exception(e: Exception) -> str:
    if isinstance(e, ValueError):
        st.error(f"🛡️ {e}")   # This will show the guardrail's custom message
        return "security_violation"
    else:
        st.error(f"Error: {e}")
        return "general_error"

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
            is_active = chat_id == st.session_state.current_chat_id

            st.markdown('<div class="chat-row-container">', unsafe_allow_html=True)
            cols = st.columns([0.85, 0.15], gap="small")
            with cols[0]:
                btn_label = f"{'🟢' if is_active else '💬'} {title[:28]}{'...' if len(title) > 28 else ''}"
                st.button(
                    btn_label,
                    key=f"chat_btn_{chat_id}",
                    use_container_width=True,
                    on_click=open_chat_callback,
                    args=(chat_id,),
                )
            with cols[1]:
                st.button(
                    "🗑️",
                    key=f"del_{chat_id}",
                    on_click=delete_chat_callback,
                    args=(chat_id,),
                )
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
    # (Dashboard code – unchanged)
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
                try:
                    response = run_chat(search_query.strip(), history=[], document_context=st.session_state.chats[new_id].get("scanned_context", ""))
                except Exception as e:
                    handle_agent_exception(e)
                    response = "I cannot process that request due to security reasons."
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
elif view == "Planner":
    st.markdown("""<div class="dashboard-card-box"><h1>📋 Planner Agent</h1><p>&nbsp;&nbsp;&nbsp;&nbsp;Generate a detailed, structured study plan.</p></div>""", unsafe_allow_html=True)

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
                try:
                    plan = run_planner(topic=topic.strip(), duration_days=int(days), context_notes=context)
                except Exception as e:
                    handle_agent_exception(e)
                    st.stop()

                if not isinstance(plan, dict) or "subtopics" not in plan:
                    st.error("❌ Failed to generate a valid study plan. Please check your API key and try again.")
                    st.stop()

                plan_text = f"## 📚 Study Plan: {plan.get('topic', topic)}\n\n"
                plan_text += f"*{plan.get('overview', '')}*\n\n"
                for sub in plan.get("subtopics", []):
                    plan_text += f"### 📅 Day {sub.get('day')} — {sub.get('title')}\n\n"
                    if sub.get("description"):
                        plan_text += f"{sub['description']}\n\n"
                    if sub.get("objectives"):
                        plan_text += "**Learning Objectives:**\n"
                        for obj in sub["objectives"]:
                            plan_text += f"- {obj}\n"
                        plan_text += "\n"
                    if sub.get("key_concepts"):
                        plan_text += "**Key Concepts:**\n"
                        for kc in sub["key_concepts"]:
                            plan_text += f"- {kc}\n"
                        plan_text += "\n"
                    if sub.get("practice"):
                        plan_text += "**Practice Tasks:**\n"
                        for task in sub["practice"]:
                            plan_text += f"- {task}\n"
                        plan_text += "\n"
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
                    "content": plan_text,
                    "plan_data": plan,
                })
                save_persistent_state()
            st.markdown(plan_text)

    if st.session_state.planner_output:
        # ── All buttons in a single row ──────────────────────────────────
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📝 Quiz on this topic", type="primary", use_container_width=True):
                st.session_state.quiz_state["prefill_topic"] = topic if topic.strip() else "General Study"
                st.session_state.quiz_state["prefill_context"] = st.session_state.planner_output
                st.session_state.current_view = "Quiz Agent"
                st.rerun()
        with col2:
            plan_json_str = json.dumps(
                st.session_state.planner_history[-1] if st.session_state.planner_history else {"content": st.session_state.planner_output},
                indent=2, ensure_ascii=False
            )
            st.download_button(
                "⬇️ JSON",
                data=plan_json_str,
                file_name=f"study_plan_{(topic or 'topic').replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
            )
        with col3:
            pdf_data = markdown_to_pdf(st.session_state.planner_output, title=f"Study Plan: {topic}")
            st.download_button(
                "⬇️ PDF",
                data=pdf_data,
                file_name=f"study_plan_{(topic or 'topic').replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

# ========== Researcher ====================================================
elif view == "Researcher":
    st.markdown("""<div class="dashboard-card-box"><h1>🔬 Researcher Agent</h1><p>&nbsp;&nbsp;&nbsp;&nbsp;Researches a topic, summarizes notes, and keeps sources visible.</p></div>""", unsafe_allow_html=True)

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
                search_q = (focus.strip() or topic.strip()) if use_web else None
                context = doc_context if use_docs else ""
                try:
                    result = run_researcher(
                        subtopic=topic.strip(),
                        search_query=search_q,
                        document_context=context,
                        history=history
                    )
                except Exception as e:
                    handle_agent_exception(e)
                    st.stop()

                notes = result["text"]
                doc_id = result.get("doc_id", "")
                st.session_state.researcher_output = notes
                st.session_state.research_history.append({
                    "topic": topic,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "content": notes,
                    "doc_id": doc_id,
                })
                save_persistent_state()
            st.markdown(notes)

    if st.session_state.researcher_output:
        # ── All buttons in a single row ──────────────────────────────────
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📝 Quiz on this topic", type="primary", use_container_width=True):
                st.session_state.quiz_state["prefill_topic"] = topic if topic.strip() else "General Research"
                st.session_state.quiz_state["prefill_context"] = st.session_state.researcher_output
                st.session_state.current_view = "Quiz Agent"
                st.rerun()
        with col2:
            research_json_str = json.dumps(
                st.session_state.research_history[-1] if st.session_state.research_history else {"content": st.session_state.researcher_output},
                indent=2, ensure_ascii=False
            )
            st.download_button(
                "⬇️ JSON",
                data=research_json_str,
                file_name=f"research_{(topic or 'topic').replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
            )
        with col3:
            pdf_data = markdown_to_pdf(st.session_state.researcher_output, title=f"Research: {topic}")
            st.download_button(
                "⬇️ PDF",
                data=pdf_data,
                file_name=f"research_{(topic or 'topic').replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

# ========== Quiz Agent ====================================================
elif view == "Quiz Agent":
    st.markdown("""<div class="dashboard-card-box"><h1>📝 Quiz Agent</h1><p>&nbsp;&nbsp;&nbsp;&nbsp;Creates MCQs, scores them, and re‑routes weak topics to Researcher Agent.</p></div>""", unsafe_allow_html=True)
    qs = st.session_state.quiz_state

    if not qs["active"]:
        use_docs = st.checkbox("Include uploaded documents", value=True, key="quiz_use_docs")
        col1, col2 = st.columns(2)
        with col1:
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
                    if use_docs:
                        hits = retrieve_notes(topic, n_results=3)
                        if hits:
                            notes = "\n\n".join(h["content"] for h in hits)
                    prefill_context = qs.get("prefill_context", "")
                    if prefill_context:
                        notes += f"\n\n--- Additional context from planner/researcher ---\n{prefill_context}"
                    try:
                        quiz_data = generate_quiz(
                            notes or f"Generate a quiz about {topic}",
                            subtopic=topic,
                            num_questions=int(num_q)
                        )
                    except Exception as e:
                        handle_agent_exception(e)
                        st.stop()

                    if not isinstance(quiz_data, dict) or "questions" not in quiz_data or not quiz_data["questions"]:
                        st.error("❌ Failed to generate quiz. Please check your API key and try again.")
                        st.stop()

                    qs["questions"] = quiz_data["questions"]
                    qs["active"] = True
                    qs["current_q"] = 0
                    qs["answers"] = {}
                    qs["finished"] = False
                    qs["score"] = 0
                    qs["session_id"] = str(uuid.uuid4())
                    qs["topic"] = topic
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
                            try:
                                quiz_doc_id = store_quiz_result(
                                    topic=qs["topic"],
                                    score=qs["score"]/100,
                                    passed=qs["score"] >= 60,
                                    retries=0,
                                    metadata={"session_id": qs.get("session_id", "")}
                                )
                            except Exception as e:
                                handle_agent_exception(e)
                                st.stop()
                            st.session_state.chromadb_mock_store.append({
                                "topic": qs["topic"],
                                "score": qs["score"],
                                "total_questions": total,
                                "correct": correct_cnt,
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "questions": qs["questions"],
                                "user_answers": {str(k): v for k, v in qs["answers"].items()},
                                "session_id": qs.get("session_id", ""),
                                "doc_id": quiz_doc_id,
                            })
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
                        try:
                            notes_result = run_researcher(
                                subtopic=qs["topic"],
                                search_query=f"{qs['topic']} explained in detail with examples",
                                document_context="",
                                history=[]
                            )
                            notes = notes_result["text"]
                            st.session_state.researcher_output = notes
                            st.session_state.current_view = "Researcher"
                            qs["active"] = False
                        except Exception as e:
                            handle_agent_exception(e)
                    st.rerun()

            latest_record = st.session_state.chromadb_mock_store[-1] if st.session_state.chromadb_mock_store else {
                "topic": qs["topic"], "score": qs["score"], "questions": qs["questions"],
                "user_answers": {str(k): v for k, v in qs["answers"].items()},
            }
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "⬇️ JSON",
                    data=json.dumps(latest_record, indent=2, ensure_ascii=False),
                    file_name=f"quiz_{(qs['topic'] or 'result').replace(' ', '_')}_{score}pct.json",
                    mime="application/json",
                )
            with col_dl2:
                # PDF
                summary_text = f"# Quiz Result: {qs['topic']}\n\n"
                summary_text += f"**Score:** {score}%\n\n"
                summary_text += f"**Correct:** {qs.get('correct', 0)}/{len(qs['questions'])}\n\n"
                summary_text += "## Detailed Answers\n\n"
                for idx, q in enumerate(qs['questions']):
                    user_ans = qs['answers'].get(idx, "Not answered")
                    correct = q['answer']
                    summary_text += f"**Q{idx+1}:** {q['question']}\n"
                    summary_text += f"- Your answer: {user_ans}\n"
                    summary_text += f"- Correct answer: {correct}\n\n"
                pdf_data = markdown_to_pdf(summary_text, title=f"Quiz Result: {qs['topic']}")
                st.download_button(
                    "⬇️ PDF",
                    data=pdf_data,
                    file_name=f"quiz_{(qs['topic'] or 'result').replace(' ', '_')}_{score}pct.pdf",
                    mime="application/pdf",
                )

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
        if st.session_state.chats:
            st.session_state.current_chat_id = list(st.session_state.chats.keys())[-1]
            st.rerun()
        else:
            st.warning("⚠️ No chats available. Create a new chat to start.")
            if st.button("Create New Chat", key="create_from_chat"):
                new_chat_callback()
                st.rerun()
            st.stop()

    chat_id = st.session_state.current_chat_id
    chat = st.session_state.chats[chat_id]
    messages = chat["messages"]

    # Header with download buttons
    col_title, col_dl1, col_dl2 = st.columns([5, 1, 1])
    with col_title:
        st.caption(f"Active session: **{chat['title']}**  ·  {len(messages)} messages")
    with col_dl1:
        st.download_button(
            "⬇️ JSON",
            data=build_chat_export(chat_id),
            file_name=f"chat_{chat['title'].replace(' ', '_')[:30]}.json",
            mime="application/json",
            key=f"dl_chat_{chat_id}",
            use_container_width=True,
        )
    with col_dl2:
        pdf_data = chat_to_pdf(chat_id)
        st.download_button(
            "⬇️ PDF",
            data=pdf_data,
            file_name=f"chat_{chat['title'].replace(' ', '_')[:30]}.pdf",
            mime="application/pdf",
            key=f"dl_pdf_chat_{chat_id}",
            use_container_width=True,
        )

    st.markdown('<div class="info-callout">💡 <strong>Tip:</strong> Upload PDFs, images, or text to ground your conversation.</div>', unsafe_allow_html=True)

    # ── PERSISTENT GUARD ERROR DISPLAY ──────────────────────────────────
    if st.session_state.guard_error_message:
        with st.chat_message("assistant"):
            st.error(st.session_state.guard_error_message)

    # ── Normal chat message display ─────────────────────────────────────
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
                extracted = handle_file_upload(uploaded_files, chat_id)
            st.success("🔍 Document scanned and parsed successfully!")
            with st.expander("📄 View extracted content", expanded=True):
                st.text_area("Extracted text", extracted, height=200)
            preview = extracted[:1500] + ("..." if len(extracted) > 1500 else "")
            chat["messages"].append({
                "role": "assistant",
                "content": f"📄 I've read the uploaded file(s). Here's a preview:\n\n{preview}\n\nYou can ask me questions about this content."
            })
            st.session_state.show_upload[upload_key] = False
            save_persistent_state()
            st.rerun()

    if st.button("🧹 Clear current chat", key="clear_chat"):
        delete_uploaded_files(chat_id)
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
            try:
                # Only pass clean history (skip blocked orphan messages)
                clean_history = build_clean_history(chat["messages"][:-1])
                response = run_chat(prompt, history=clean_history, document_context=context)
                # Success → add assistant message and clear persistent error
                chat["messages"].append({"role": "assistant", "content": response})
                st.session_state.guard_error_message = None
            except ValueError as ve:
                # Guardrail violation → store persistent error, user message stays
                st.session_state.guard_error_message = f"🛡️ {ve}"
            except Exception as e:
                st.error(f"Error: {e}")
                chat["messages"].append({"role": "assistant", "content": f"Error: {e}"})
        save_persistent_state()
        st.rerun()

# ========== History ========================================================
elif view == "History":
    st.title("📜 Activity History")
    st.caption("Review all your past activities.")

    col_title, col_dl_all = st.columns([5, 1])
    with col_dl_all:
        st.download_button(
            "⬇️ Export All (JSON)",
            data=build_full_export(),
            file_name=f"study_buddy_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

    # ── Delete helpers ─────────────────────────────────────────────────────
    def delete_chat_from_history(chat_id: str):
        delete_uploaded_files(chat_id)
        if chat_id in st.session_state.chats:
            del st.session_state.chats[chat_id]
        if st.session_state.current_chat_id == chat_id:
            remaining = list(st.session_state.chats.keys())
            st.session_state.current_chat_id = remaining[-1] if remaining else None
        conv_file = Path("data/conversations") / f"{chat_id}.json"
        if conv_file.exists():
            conv_file.unlink()
        save_persistent_state()

    def delete_quiz(index: int):
        if 0 <= index < len(st.session_state.chromadb_mock_store):
            record = st.session_state.chromadb_mock_store[index]
            doc_id = record.get("doc_id")
            if doc_id:
                try:
                    delete_document(doc_id)
                except Exception:
                    pass
            session_id = record.get("session_id", "")
            if session_id:
                quiz_file = Path("data/quiz_history") / f"{session_id}.json"
                if quiz_file.exists():
                    quiz_file.unlink()
            del st.session_state.chromadb_mock_store[index]
            save_persistent_state()

    def delete_research(index: int):
        if 0 <= index < len(st.session_state.research_history):
            entry = st.session_state.research_history[index]
            doc_id = entry.get("doc_id")
            if doc_id:
                try:
                    delete_document(doc_id)
                except Exception:
                    pass
            del st.session_state.research_history[index]
            save_persistent_state()

    def delete_planner(index: int):
        if 0 <= index < len(st.session_state.planner_history):
            del st.session_state.planner_history[index]
            save_persistent_state()

    # ── Tabs ──────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat History", "📝 Quiz History", "🔬 Research History", "📋 Planner History"])

    with tab1:
        st.subheader("Chat Sessions")
        if st.session_state.chats:
            for chat_id, chat_data in st.session_state.chats.items():
                col_left, col_right = st.columns([0.7, 0.3])
                with col_left:
                    with st.expander(f"Chat: {chat_data['title']} ({len(chat_data['messages'])} messages)"):
                        st.write(f"**Created:** {chat_data['timestamp']}")
                        if chat_data["messages"]:
                            first_msg = chat_data["messages"][0]["content"][:100]
                            st.write(f"**First message:** {first_msg}...")
                        st.button(
                            "Open this chat",
                            key=f"hist_open_{chat_id}",
                            on_click=open_chat_callback,
                            args=(chat_id,),
                        )
                with col_right:
                    # Order: PDF, JSON, Delete
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        pdf_data = chat_to_pdf(chat_id)
                        st.download_button(
                            "⬇️ PDF",
                            data=pdf_data,
                            file_name=f"chat_{chat_data['title'].replace(' ', '_')[:30]}.pdf",
                            mime="application/pdf",
                            key=f"hist_dl_pdf_chat_{chat_id}",
                            use_container_width=True,
                        )
                    with b2:
                        json_data = build_chat_export(chat_id)
                        st.download_button(
                            "⬇️ JSON",
                            data=json_data,
                            file_name=f"chat_{chat_data['title'].replace(' ', '_')[:30]}.json",
                            mime="application/json",
                            key=f"hist_dl_json_chat_{chat_id}",
                            use_container_width=True,
                        )
                    with b3:
                        if st.button("🗑️ DELETE", key=f"del_chat_hist_{chat_id}", use_container_width=True):
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
                col_left, col_right = st.columns([0.7, 0.3])
                with col_left:
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
                with col_right:
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        # PDF
                        summary_text = f"# Quiz Result: {record['topic']}\n\n"
                        summary_text += f"**Score:** {record['score']}%\n\n"
                        summary_text += f"**Correct:** {record['correct']}/{record['total_questions']}\n\n"
                        summary_text += "## Detailed Answers\n\n"
                        for q_idx, q in enumerate(record["questions"]):
                            user_ans = record["user_answers"].get(str(q_idx), "No answer")
                            correct_ans = q["answer"]
                            summary_text += f"**Q{q_idx+1}:** {q['question']}\n"
                            summary_text += f"- Your answer: {user_ans}\n"
                            summary_text += f"- Correct answer: {correct_ans}\n\n"
                        pdf_data = markdown_to_pdf(summary_text, title=f"Quiz Result: {record['topic']}")
                        st.download_button(
                            "⬇️ PDF",
                            data=pdf_data,
                            file_name=f"quiz_{record['topic'].replace(' ', '_')}_{record['score']}pct.pdf",
                            mime="application/pdf",
                            key=f"hist_dl_pdf_quiz_{idx}",
                            use_container_width=True,
                        )
                    with b2:
                        # JSON
                        json_data = json.dumps(record, indent=2, ensure_ascii=False)
                        st.download_button(
                            "⬇️ JSON",
                            data=json_data,
                            file_name=f"quiz_{record['topic'].replace(' ', '_')}_{record['score']}pct.json",
                            mime="application/json",
                            key=f"hist_dl_json_quiz_{idx}",
                            use_container_width=True,
                        )
                    with b3:
                        # Delete
                        if st.button("🗑️ DELETE", key=f"del_quiz_{idx}", use_container_width=True):
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
                col_left, col_right = st.columns([0.7, 0.3])
                with col_left:
                    with st.expander(f"Research {idx+1}: {entry['topic']} ({entry['timestamp']})"):
                        st.markdown(entry["content"])
                with col_right:
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        # PDF
                        pdf_data = markdown_to_pdf(entry["content"], title=f"Research: {entry['topic']}")
                        st.download_button(
                            "⬇️ PDF",
                            data=pdf_data,
                            file_name=f"research_{entry['topic'].replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"hist_dl_pdf_research_{idx}",
                            use_container_width=True,
                        )
                    with b2:
                        # JSON
                        json_data = json.dumps(entry, indent=2, ensure_ascii=False)
                        st.download_button(
                            "⬇️ JSON",
                            data=json_data,
                            file_name=f"research_{entry['topic'].replace(' ', '_')}.json",
                            mime="application/json",
                            key=f"hist_dl_json_research_{idx}",
                            use_container_width=True,
                        )
                    with b3:
                        # Delete
                        if st.button("🗑️ DELETE", key=f"del_research_{idx}", use_container_width=True):
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
                col_left, col_right = st.columns([0.7, 0.3])
                with col_left:
                    with st.expander(f"Plan {idx+1}: {entry['topic']} ({entry['timestamp']})"):
                        st.markdown(entry["content"])
                with col_right:
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        # PDF
                        pdf_data = markdown_to_pdf(entry["content"], title=f"Study Plan: {entry['topic']}")
                        st.download_button(
                            "⬇️ PDF",
                            data=pdf_data,
                            file_name=f"plan_{entry['topic'].replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            key=f"hist_dl_pdf_planner_{idx}",
                            use_container_width=True,
                        )
                    with b2:
                        # JSON
                        json_data = json.dumps(entry, indent=2, ensure_ascii=False)
                        st.download_button(
                            "⬇️ JSON",
                            data=json_data,
                            file_name=f"plan_{entry['topic'].replace(' ', '_')}.json",
                            mime="application/json",
                            key=f"hist_dl_json_planner_{idx}",
                            use_container_width=True,
                        )
                    with b3:
                        # Delete
                        if st.button("🗑️ DELETE", key=f"del_planner_{idx}", use_container_width=True):
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

    st.download_button(
        "⬇️ Export everything (JSON)",
        data=build_full_export(),
        file_name=f"study_buddy_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
    )

    if st.button("🗑️ Wipe all persistent data (cannot be undone)", type="primary"):
        clear_all()
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
            os.makedirs(UPLOAD_DIR, exist_ok=True)
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