"""
agents/researcher_agent.py — Fetches web content and summarises it into study notes
"""
from __future__ import annotations
from tools.search_tool import web_search, format_search_results
from memory.vector_store import store_note
from utils.llm_client import chat

SYSTEM = """You are an expert academic researcher and tutor.
Given a subtopic and raw web search results (or uploaded document content), write clear, structured study notes that a student can learn from.

Format your notes with:
- ## Overview
- ## Key Concepts (bullet points)
- ## Important Details
- ## Summary

Be concise, accurate, and educational. Aim for 300–500 words."""

def run_researcher(
    subtopic: str,
    search_query: str | None = None,
    document_context: str = "",
    history: list[dict] | None = None,
) -> dict:
    """
    Research a subtopic via web search and/or document context.
    Stores the resulting note in ChromaDB.
    Returns a dict: {"text": <note text>, "doc_id": <ChromaDB document ID>}
    """
    search_results_text = ""

    if search_query or subtopic:
        query = search_query or subtopic
        results = web_search(query)
        search_results_text = format_search_results(results)

    user_parts = [f"Subtopic: {subtopic}"]
    if document_context:
        user_parts.append(f"\n\n--- Uploaded Document Content ---\n{document_context[:4000]}")
    if search_results_text:
        user_parts.append(f"\n\n--- Web Search Results ---\n{search_results_text}")

    messages = []
    if history:
        messages.extend(history[-4:])
    messages.append({"role": "user", "content": "\n".join(user_parts)})

    note = chat(messages=messages, system=SYSTEM, temperature=0.5, max_tokens=1500)

    # Store in vector store and capture the doc_id
    doc_id = store_note(subtopic=subtopic, content=note, source="researcher")

    return {
        "text": note,
        "doc_id": doc_id
    }