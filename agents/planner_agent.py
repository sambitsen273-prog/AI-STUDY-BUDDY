"""
agents/planner_agent.py — Generates a structured JSON study plan (detailed)
"""
from __future__ import annotations
from utils.llm_client import chat, parse_json_response

SYSTEM_TEMPLATE = """You are an expert educational planner. Create a comprehensive, detailed study plan with thorough daily breakdowns.

IMPORTANT: The plan must have exactly {duration} days. Do not exceed or reduce this number.

For each day, provide:
- A descriptive title
- A detailed explanation of what will be learned (at least 2-3 sentences)
- Specific learning objectives (at least 3)
- Key concepts with brief explanations
- Recommended resources (books, articles, videos) or practice tasks
- Optional: practice tasks or hands-on exercises

Respond with a valid JSON object following this schema:
{{
  "topic": "<main topic>",
  "duration_days": {duration},
  "overview": "<2-3 sentence overview of the whole course>",
  "subtopics": [
    {{
      "day": <int>,
      "title": "<day title>",
      "description": "<detailed paragraph explaining what will be covered, why it matters, and what the learner will achieve>",
      "objectives": ["objective 1", "objective 2", "objective 3", ...],
      "key_concepts": ["concept 1", "concept 2", ...],
      "resources": ["resource 1 (with description)", "resource 2", ...],
      "practice": ["practice task 1", "practice task 2", ...]
    }}
    // ... exactly {duration} items
  ]
}}

Ensure the JSON is strictly valid — no trailing commas, no extra text. Make the content educational, clear, and practical."""

def run_planner(topic: str, duration_days: int = 5, context_notes: str = "") -> dict:
    """
    Returns a detailed study plan dict with exactly duration_days days.
    If context_notes is provided (e.g. from uploaded docs), the plan is tailored to that content.
    """
    user_content = f"Topic: {topic}\nDuration: {duration_days} days"
    if context_notes:
        user_content += f"\n\nAdditional context from uploaded materials:\n{context_notes[:3000]}"

    system_prompt = SYSTEM_TEMPLATE.format(duration=duration_days)

    # First attempt with full context
    try:
        response = chat(
            messages=[{"role": "user", "content": user_content}],
            system=system_prompt,
            temperature=0.4,
            max_tokens=4000,
            json_mode=True,
        )
        plan = parse_json_response(response)
    except Exception as e:
        print(f"⚠️ Planner first attempt failed: {e}. Retrying with simpler prompt...")
        # Retry with a shorter, simpler prompt to avoid truncation
        try:
            response = chat(
                messages=[{"role": "user", "content": f"Topic: {topic}\nDuration: {duration_days} days"}],
                system=system_prompt,
                temperature=0.5,
                max_tokens=4000,
                json_mode=True,
            )
            plan = parse_json_response(response)
        except Exception as e2:
            print(f"⚠️ Planner retry failed: {e2}. Using fallback.")
            # Fallback: generate all days
            plan = {
                "topic": topic,
                "duration_days": duration_days,
                "overview": f"Comprehensive study plan for {topic} over {duration_days} days.",
                "subtopics": [
                    {
                        "day": i+1,
                        "title": f"Day {i+1}: Core concepts",
                        "description": f"Detailed exploration of fundamental {topic} concepts. This day covers essential theory and practical applications.",
                        "objectives": ["Understand fundamental concepts", "Apply knowledge in exercises"],
                        "key_concepts": ["Concept A", "Concept B"],
                        "resources": [f"{topic} beginner tutorial"],
                        "practice": ["Complete practice exercise 1", "Review class notes"]
                    } for i in range(duration_days)
                ]
            }

    # Normalise: ensure all subtopics have required fields and exactly duration_days
    if "subtopics" not in plan:
        plan["subtopics"] = []
    # If the model returned fewer days than requested, pad with fallback
    while len(plan["subtopics"]) < duration_days:
        day_num = len(plan["subtopics"]) + 1
        plan["subtopics"].append({
            "day": day_num,
            "title": f"Day {day_num}: Additional topics",
            "description": f"Further exploration of {topic} concepts.",
            "objectives": ["Review core concepts", "Practice applications"],
            "key_concepts": ["Concept C", "Concept D"],
            "resources": ["Additional resources"],
            "practice": ["Practice exercise"]
        })
    # Truncate if too many (should not happen)
    if len(plan["subtopics"]) > duration_days:
        plan["subtopics"] = plan["subtopics"][:duration_days]

    for sub in plan["subtopics"]:
        sub.setdefault("description", f"Day {sub.get('day', '?')} study content.")
        sub.setdefault("practice", [])
        sub.setdefault("resources", [])

    return plan