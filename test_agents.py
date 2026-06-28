"""
test_agents.py — Quick smoke-test of all agents (mocks Mistral API)
Run: python test_agents.py
"""
import sys, json
from unittest.mock import patch, MagicMock

MOCK_PLAN = json.dumps({
    "topic": "Python Basics",
    "duration_days": 2,
    "overview": "Learn Python fundamentals.",
    "subtopics": [
        {
            "day": 1,
            "title": "Variables & Data Types",
            "objectives": ["Understand int, str, list"],
            "key_concepts": ["int", "str", "list", "dict"],
            "resources": ["Python variables tutorial"],
        }
    ],
})

MOCK_NOTES = """## Overview
Python variables store data values. Unlike other languages, you don't need to declare type.

## Key Concepts
- int: whole numbers (42)
- str: text ("hello")
- list: ordered collection ([1, 2, 3])
- dict: key-value pairs ({"name": "Alice"})

## Important Details
Variables are dynamically typed. Use type() to check.

## Summary
Python's variable system is simple and flexible."""

MOCK_QUIZ = json.dumps({
    "questions": [
        {
            "id": 1,
            "question": "What data type stores whole numbers in Python?",
            "options": {"A": "str", "B": "int", "C": "float", "D": "list"},
            "answer": "B",
            "explanation": "int stores whole numbers like 42.",
        },
        {
            "id": 2,
            "question": "Which data type stores key-value pairs?",
            "options": {"A": "list", "B": "tuple", "C": "dict", "D": "set"},
            "answer": "C",
            "explanation": "dict stores key-value pairs.",
        },
        {
            "id": 3,
            "question": "How do you check the type of a variable?",
            "options": {"A": "typeof()", "B": "gettype()", "C": "type()", "D": "vartype()"},
            "answer": "C",
            "explanation": "type() returns the data type of a variable.",
        },
        {
            "id": 4,
            "question": "What does str stand for?",
            "options": {"A": "structure", "B": "string", "C": "strict", "D": "stream"},
            "answer": "B",
            "explanation": "str is short for string — text data.",
        },
        {
            "id": 5,
            "question": "Are Python variables statically or dynamically typed?",
            "options": {"A": "statically", "B": "dynamically", "C": "both", "D": "neither"},
            "answer": "B",
            "explanation": "Python uses dynamic typing — no need to declare types.",
        },
    ]
})

MOCK_SCORE = json.dumps({
    "score": 0.8,
    "correct_count": 4,
    "total": 5,
    "feedback": [
        {"question_id": 1, "correct": True,  "student_answer": "B", "correct_answer": "B", "explanation": "Correct!"},
        {"question_id": 2, "correct": True,  "student_answer": "C", "correct_answer": "C", "explanation": "Correct!"},
        {"question_id": 3, "correct": True,  "student_answer": "C", "correct_answer": "C", "explanation": "Correct!"},
        {"question_id": 4, "correct": False, "student_answer": "A", "correct_answer": "B", "explanation": "str = string"},
        {"question_id": 5, "correct": True,  "student_answer": "B", "correct_answer": "B", "explanation": "Correct!"},
    ],
    "overall_feedback": "Great job! A little more review on abbreviations and you'll be perfect.",
})

MOCK_COACH = "Excellent effort! You clearly understand the core concepts. Just brush up on str meaning string."
MOCK_CHAT  = "Python variables are containers that store data values. They're dynamically typed!"

CALL_COUNTER = [0]
def mock_chat(messages, **kwargs):
    i = CALL_COUNTER[0] % 6
    CALL_COUNTER[0] += 1
    return [MOCK_PLAN, MOCK_NOTES, MOCK_QUIZ, MOCK_SCORE, MOCK_COACH, MOCK_CHAT][i]

def mock_web_search(query, **kwargs):
    return [{"title": "Python Tutorial", "url": "https://example.com", "content": "Python basics explained."}]

def mock_store_note(*a, **kw): return "abc123"
def mock_retrieve_notes(*a, **kw): return [{"subtopic": "Variables", "content": MOCK_NOTES, "source": "researcher"}]
def mock_get_count(): return 5


def run_tests():
    passed = failed = 0

    with patch("utils.llm_client.requests") as mock_req, \
         patch("tools.search_tool.requests") as mock_sreq, \
         patch("memory.vector_store.chromadb") as mock_chroma:

        # Setup mocks
        mock_resp = MagicMock()
        mock_resp.json.side_effect = lambda: {
            "choices": [{"message": {"content": mock_chat([])}}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_req.post.return_value = mock_resp

        mock_sresp = MagicMock()
        mock_sresp.json.return_value = {"results": [], "answer": "Python is great"}
        mock_sresp.raise_for_status = MagicMock()
        mock_sreq.post.return_value = mock_sresp

        col = MagicMock()
        col.count.return_value = 5
        col.query.return_value = {
            "documents": [[MOCK_NOTES]],
            "metadatas": [[{"subtopic": "Variables", "source": "researcher"}]],
        }
        col.get.return_value = {"ids": ["1"], "metadatas": [{"subtopic": "Variables"}]}
        mock_chroma.PersistentClient.return_value.get_or_create_collection.return_value = col

        tests = [
            ("Config loads",          test_config),
            ("LLM client",            test_llm_client),
            ("File extractor (txt)",  test_file_extractor),
            ("Search tool",           test_search_tool),
            ("Planner agent",         test_planner),
            ("Quiz generation",       test_quiz),
            ("Quiz scoring",          test_score),
            ("Vector store",          test_vector_store),
        ]

        for name, fn in tests:
            try:
                fn()
                print(f"  ✅ {name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


def test_config():
    import config
    assert hasattr(config, "MISTRAL_API_KEY")
    assert hasattr(config, "QUIZ_PASS_SCORE")
    assert config.QUIZ_PASS_SCORE == 0.6

def test_llm_client():
    import utils.llm_client as lc
    import json
    result = lc.parse_json_response('{"key": "value"}')
    assert result == {"key": "value"}
    result2 = lc.parse_json_response('```json\n{"a": 1}\n```')
    assert result2 == {"a": 1}

def test_file_extractor():
    import tempfile, os
    from utils.file_extractor import extract_text
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello, Study Buddy!")
        name = f.name
    try:
        text = extract_text(name)
        assert "Hello" in text
    finally:
        os.unlink(name)

def test_search_tool():
    from tools.search_tool import format_search_results
    results = [{"title": "Test", "url": "http://x.com", "content": "content"}]
    formatted = format_search_results(results)
    assert "Test" in formatted

def test_planner():
    import json
    from unittest.mock import patch
    with patch("utils.llm_client.requests") as mr:
        r = MagicMock()
        r.json.return_value = {"choices": [{"message": {"content": MOCK_PLAN}}]}
        r.raise_for_status = MagicMock()
        mr.post.return_value = r
        from agents.planner_agent import run_planner
        plan = run_planner("Python Basics", 2)
        assert "subtopics" in plan
        assert len(plan["subtopics"]) >= 1

def test_quiz():
    import json
    from unittest.mock import patch
    with patch("utils.llm_client.requests") as mr:
        r = MagicMock()
        r.json.return_value = {"choices": [{"message": {"content": MOCK_QUIZ}}]}
        r.raise_for_status = MagicMock()
        mr.post.return_value = r
        from agents.quiz_agent import generate_quiz
        quiz = generate_quiz(MOCK_NOTES, "Variables")
        assert "questions" in quiz
        assert len(quiz["questions"]) == 5

def test_score():
    import json
    from unittest.mock import patch
    with patch("utils.llm_client.requests") as mr:
        r = MagicMock()
        r.json.return_value = {"choices": [{"message": {"content": MOCK_SCORE}}]}
        r.raise_for_status = MagicMock()
        mr.post.return_value = r
        from agents.quiz_agent import score_quiz
        questions = json.loads(MOCK_QUIZ)["questions"]
        answers   = {1: "B", 2: "C", 3: "C", 4: "A", 5: "B"}
        result    = score_quiz(questions, answers)
        assert "score" in result
        assert 0 <= result["score"] <= 1

def test_vector_store():
    from unittest.mock import patch, MagicMock
    with patch("memory.vector_store.chromadb") as mc:
        col = MagicMock()
        col.count.return_value = 0
        mc.PersistentClient.return_value.get_or_create_collection.return_value = col
        # Reset the singleton
        import memory.vector_store as vs
        vs._collection = None
        vs._client     = None
        uid = vs.store_note("Test topic", "Test content")
        assert col.add.called


if __name__ == "__main__":
    print("\n🧪 AI Study Buddy — Test Suite\n" + "="*40)
    ok = run_tests()
    sys.exit(0 if ok else 1)
