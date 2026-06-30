"""
agents/chat_agent.py — Conversational Q&A with memory and document awareness
"""
from __future__ import annotations
import logging
from memory.vector_store import retrieve_notes
from utils.llm_client import chat
from config import MISTRAL_API_KEY, MAX_HISTORY_TURNS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    """
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set. Please add it to your .env file.")

    # 1. Retrieve relevant notes from vector store (long-term memory)
    relevant_notes = retrieve_notes(user_message, n_results=3)
    notes_text = ""
    if relevant_notes:
        notes_text = "\n\n".join(
            f"[Note on '{n['subtopic']}']\n{n['content'][:600]}"
            for n in relevant_notes
        )

    # 2. Build system context (but limit to avoid token overflow)
    context_parts = [SYSTEM]
    if notes_text:
        context_parts.append(f"\n\n=== Relevant Study Notes from Memory ===\n{notes_text[:2000]}")
    if document_context:
        # Truncate aggressively
        truncated_doc = document_context[:3000] + ("..." if len(document_context) > 3000 else "")
        context_parts.append(f"\n\n=== Uploaded Document Content ===\n{truncated_doc}")
    full_system = "\n".join(context_parts)

    # 3. Short-term history (last 3 turns)
    trimmed_history = history[-(MAX_HISTORY_TURNS * 2):]
    messages = trimmed_history + [{"role": "user", "content": user_message}]

    # 4. First attempt with full context
    try:
        response = chat(
            messages=messages,
            system=full_system,
            temperature=0.7,
            max_tokens=2000,
        )
        if response and response.strip():
            return response.strip()
        else:
            raise RuntimeError("Empty response from Mistral (first attempt).")
    except Exception as e:
        logger.error(f"First chat attempt failed: {e}")
        # Retry with simplified system prompt and shorter context
        try:
            simple_system = "You are a helpful tutor. Answer the user's question clearly and concisely."
            # Use only the last 2 messages, no notes/context
            short_history = history[-4:] if history else []
            simple_messages = short_history + [{"role": "user", "content": user_message}]
            response = chat(
                messages=simple_messages,
                system=simple_system,
                temperature=0.7,
                max_tokens=1500,
            )
            if response and response.strip():
                return response.strip()
            else:
                raise RuntimeError("Empty response from Mistral (retry).")
        except Exception as e2:
            logger.error(f"Retry failed: {e2}")
            # Final fallback: return a friendly error message
            return f"I'm having trouble reaching the AI service. Please check your Mistral API key and try again. (Error: {str(e2)})"