"""
tools/search_tool.py — Tavily web search integration
"""
from __future__ import annotations
import os
import requests
from config import TAVILY_API_KEY

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Perform a web search using Tavily.
    Returns list of dicts with keys: title, url, content.
    """
    if not TAVILY_API_KEY:
        return [{"title": "No Tavily key", "url": "", "content": "Set TAVILY_API_KEY in .env to enable web search."}]

    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": True,
    }
    try:
        resp = requests.post(TAVILY_SEARCH_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        answer = data.get("answer", "")
        formatted = []
        if answer:
            formatted.append({"title": "Direct Answer", "url": "", "content": answer})
        for r in results[:max_results]:
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:1000],
            })
        return formatted
    except Exception as e:
        return [{"title": "Search error", "url": "", "content": str(e)}]

def format_search_results(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] {r['title']}\n{r['content']}\nSource: {r['url']}")
    return "\n\n".join(parts)