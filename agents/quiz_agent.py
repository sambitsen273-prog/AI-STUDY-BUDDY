"""
agents/quiz_agent.py — Generates MCQs from study notes and scores answers
"""
from __future__ import annotations
import json
from utils.llm_client import chat, parse_json_response

GENERATE_SYSTEM_TEMPLATE = """You are a quiz master for students.
Given study notes, generate exactly {num} multiple-choice questions to test understanding.
Respond with ONLY valid JSON — no markdown, no preamble.

Schema:
{{
  "questions": [
    {{
      "id": 1,
      "question": "<question text>",
      "options": {{
        "A": "<option A>",
        "B": "<option B>",
        "C": "<option C>",
        "D": "<option D>"
      }},
      "answer": "<correct letter, e.g. B>",
      "explanation": "<brief explanation>"
    }}
  ]
}}"""

SCORE_SYSTEM = """You are a strict but encouraging quiz evaluator.
Given the questions, correct answers, and the student's answers, return ONLY valid JSON.

Schema:
{
  "score": <float between 0 and 1>,
  "correct_count": <int>,
  "total": <int>,
  "feedback": [
    {
      "question_id": <int>,
      "correct": <bool>,
      "student_answer": "<letter>",
      "correct_answer": "<letter>",
      "explanation": "<why>"
    }
  ],
  "overall_feedback": "<encouraging sentence>"
}"""


def _fallback_quiz(subtopic: str, num_questions: int) -> dict:
    """Used if quiz generation fails entirely, so the UI never sees None."""
    return {
        "questions": [
            {
                "id": i + 1,
                "question": f"(Auto-generated placeholder) Question {i + 1} about {subtopic or 'this topic'}?",
                "options": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
                "answer": "A",
                "explanation": "Quiz generation failed; this is a placeholder question.",
            }
            for i in range(num_questions)
        ]
    }


def generate_quiz(notes: str, subtopic: str = "", num_questions: int = 5) -> dict:
    """
    Generate num_questions MCQs from notes. Returns parsed JSON dict.
    Never returns None — falls back to a placeholder quiz on failure so
    callers can rely on `"questions" in quiz_data` being safe to check.
    """
    prompt = f"Subtopic: {subtopic}\n\nStudy Notes:\n{notes[:4000]}"
    system = GENERATE_SYSTEM_TEMPLATE.format(num=num_questions)

    try:
        resp = chat(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            temperature=0.6,
            json_mode=True,
            timeout=90,
        )
        quiz = parse_json_response(resp)
        if isinstance(quiz, dict) and quiz.get("questions"):
            return quiz
        raise ValueError("Parsed quiz JSON missing a non-empty 'questions' list")
    except Exception as e:
        print(f"⚠️ Quiz generation failed: {e}. Retrying once with a simpler prompt...")
        try:
            simple_prompt = f"Generate a quiz about: {subtopic or notes[:200]}"
            resp = chat(
                messages=[{"role": "user", "content": simple_prompt}],
                system=system,
                temperature=0.6,
                json_mode=True,
                timeout=90,
            )
            quiz = parse_json_response(resp)
            if isinstance(quiz, dict) and quiz.get("questions"):
                return quiz
            raise ValueError("Retry also missing a non-empty 'questions' list")
        except Exception as e2:
            print(f"⚠️ Quiz generation retry failed: {e2}. Using fallback quiz.")
            return _fallback_quiz(subtopic, num_questions)


def score_quiz(questions: list[dict], student_answers: dict[int, str]) -> dict:
    """
    Score the student's answers.
    student_answers: {question_id: "A"|"B"|"C"|"D"}
    Falls back to a locally-computed score if the LLM scoring call fails,
    so the UI never crashes on a None/empty result.
    """
    qa_summary = []
    for q in questions:
        qid = q["id"]
        qa_summary.append({
            "id": qid,
            "question": q["question"],
            "correct_answer": q["answer"],
            "student_answer": student_answers.get(qid, ""),
        })

    prompt = json.dumps({"questions": qa_summary})

    try:
        resp = chat(
            messages=[{"role": "user", "content": prompt}],
            system=SCORE_SYSTEM,
            temperature=0.3,
            json_mode=True,
            timeout=60,
        )
        result = parse_json_response(resp)
        if isinstance(result, dict) and "score" in result:
            return result
        raise ValueError("Parsed score JSON missing 'score' field")
    except Exception as e:
        print(f"⚠️ Quiz scoring via LLM failed: {e}. Falling back to local scoring.")
        total = len(qa_summary)
        correct_count = sum(1 for q in qa_summary if q["student_answer"] == q["correct_answer"])
        feedback = [
            {
                "question_id": q["id"],
                "correct": q["student_answer"] == q["correct_answer"],
                "student_answer": q["student_answer"],
                "correct_answer": q["correct_answer"],
                "explanation": "",
            }
            for q in qa_summary
        ]
        return {
            "score": (correct_count / total) if total else 0.0,
            "correct_count": correct_count,
            "total": total,
            "feedback": feedback,
            "overall_feedback": "Score computed locally because the AI evaluator was unavailable.",
        }