"""
memory/vector_store.py — ChromaDB persistent storage for study notes and quiz history
"""
from __future__ import annotations
import uuid
import time
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError
from config import CHROMA_DB_PATH, COLLECTION_NAME

_client = None
_collection = None

def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH, settings=Settings(anonymized_telemetry=False))
    return _client

def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        try:
            _collection = client.get_collection(COLLECTION_NAME)
        except NotFoundError:
            # Collection does not exist – create it
            _collection = client.create_collection(COLLECTION_NAME)
    return _collection

def store_note(subtopic: str, content: str, source: str = "researcher", metadata: Optional[Dict] = None) -> str:
    """
    Store a study note in ChromaDB.
    Returns the document ID.
    """
    collection = _get_collection()
    doc_id = str(uuid.uuid4())
    meta = {
        "subtopic": subtopic,
        "source": source,
        "timestamp": time.time(),
    }
    if metadata:
        meta.update(metadata)
    collection.add(
        documents=[content],
        metadatas=[meta],
        ids=[doc_id],
    )
    return doc_id

def retrieve_notes(query: str, n_results: int = 3) -> List[Dict]:
    """
    Retrieve most relevant notes based on semantic similarity.
    Returns list of dicts with keys: content, subtopic, source, metadata.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    ids = results.get("ids", [[]])[0]
    out = []
    for doc, meta, doc_id in zip(docs, metas, ids):
        out.append({
            "content": doc,
            "subtopic": meta.get("subtopic", "unknown"),
            "source": meta.get("source", "unknown"),
            "metadata": meta,
            "id": doc_id,
        })
    return out

def list_all_subtopics() -> List[str]:
    """Return a list of unique subtopics stored."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    all_meta = collection.get()["metadatas"]
    subtopics = set()
    for meta in all_meta:
        if meta and "subtopic" in meta:
            subtopics.add(meta["subtopic"])
    return list(subtopics)

def get_note_count() -> int:
    return _get_collection().count()

def clear_all() -> None:
    """Delete the entire collection and reset the global reference."""
    global _collection
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except NotFoundError:
        pass  # already gone
    _collection = None  # force re‑creation on next access

def store_quiz_result(topic: str, score: float, passed: bool, retries: int, metadata: Optional[Dict] = None) -> str:
    """
    Store a quiz result as a special note for history.
    """
    content = f"Quiz on '{topic}': Score {score*100:.1f}% - {'Passed' if passed else 'Failed'} (Retries: {retries})"
    meta = {
        "subtopic": topic,
        "source": "quiz_history",
        "score": score,
        "passed": passed,
        "retries": retries,
        "timestamp": time.time(),
    }
    if metadata:
        meta.update(metadata)
    return store_note(topic, content, source="quiz_history", metadata=meta)

def get_quiz_history(limit: int = 50) -> List[Dict]:
    """
    Retrieve all quiz history entries (source == 'quiz_history') sorted by timestamp.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []
    all_data = collection.get()
    docs = all_data["documents"]
    metas = all_data["metadatas"]
    ids = all_data["ids"]
    history = []
    for doc, meta, doc_id in zip(docs, metas, ids):
        if meta and meta.get("source") == "quiz_history":
            history.append({
                "content": doc,
                "metadata": meta,
                "id": doc_id,
            })
    history.sort(key=lambda x: x["metadata"].get("timestamp", 0), reverse=True)
    return history[:limit]

def delete_document(doc_id: str) -> None:
    """Delete a specific document by ID."""
    collection = _get_collection()
    collection.delete(ids=[doc_id])