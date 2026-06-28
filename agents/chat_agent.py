"""
agents/chat_agent.py — Conversational Q&A with memory and document awareness
"""
from __future__ import annotations
from memory.vector_store import retrieve_notes
from utils.llm_client import chat

SYSTEM = """You are AI Study Buddy — a knowledgeable, friendly tutor.
You have access to the student's own study notes stored in your memory.
Always:
- Answer questions clearly and at the right difficulty level
- Reference the student's notes when relevant
- Encourage the student and celebrate progress
- If you don't know something, say so and suggest searching or uploading a document"""

def run_chat(
    user_message: str,
    history: list[dict],
    document_context: str = "",
) -> str:
    """
    Single-turn chat with short-term history + long-term memory retrieval.
    history: list of {"role": "user"|"assistant", "content": "..."}
    """
    # Semantic retrieval from ChromaDB
    relevant_notes = retrieve_notes(user_message, n_results=3)
    notes_text = ""
    if relevant_notes:
        notes_text = "\n\n".join(
            f"[Note on '{n['subtopic']}']\n{n['content'][:600]}"
            for n in relevant_notes
        )

    # Build system context
    context_parts = [SYSTEM]
    if notes_text:
        context_parts.append(f"\n\n=== Relevant Study Notes from Memory ===\n{notes_text}")
    if document_context:
        context_parts.append(f"\n\n=== Uploaded Document Content ===\n{document_context[:3000]}")
    full_system = "\n".join(context_parts)

    # Short-term history (last MAX_HISTORY_TURNS * 2 messages)
    from config import MAX_HISTORY_TURNS
    trimmed_history = history[-(MAX_HISTORY_TURNS * 2):]
    messages = trimmed_history + [{"role": "user", "content": user_message}]

    return chat(messages=messages, system=full_system, temperature=0.7, max_tokens=1000)