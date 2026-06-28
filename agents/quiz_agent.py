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

def generate_quiz(notes: str, subtopic: str = "", num_questions: int = 5) -> dict:
    """Generate num_questions MCQs from notes. Returns parsed JSON dict."""
    prompt = f"Subtopic: {subtopic}\n\nStudy Notes:\n{notes[:4000]}"
    system = GENERATE_SYSTEM_TEMPLATE.format(num=num_questions)
    resp = chat(
        messages=[{"role": "user", "content": prompt}],
        system=system,
        temperature=0.6,
        json_mode=True,
    )
    return parse_json_response(resp)


def score_quiz(questions: list[dict], student_answers: dict[int, str]) -> dict:
    """
    Score the student's answers.
    student_answers: {question_id: "A"|"B"|"C"|"D"}
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
    resp = chat(
        messages=[{"role": "user", "content": prompt}],
        system=SCORE_SYSTEM,
        temperature=0.3,
        json_mode=True,
    )
    return parse_json_response(resp)