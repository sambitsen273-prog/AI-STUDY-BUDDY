"""
agents/planner_agent.py — Generates a structured JSON study plan (detailed)
"""
from __future__ import annotations
from utils.llm_client import chat, parse_json_response

# Large token budget and timeout for long study plans
PLANNER_MAX_TOKENS = 12000
PLANNER_TIMEOUT = 300  # 5 minutes

SYSTEM_TEMPLATE = """You are an expert educational planner. Create a comprehensive, detailed study plan with thorough daily breakdowns.

IMPORTANT: The plan must have exactly {duration} days. Do not exceed or reduce this number.

For each day, provide:
- A descriptive title
- A detailed explanation of what will be learned (at least 2-3 sentences)
- Specific learning objectives (at least 3)
- Key concepts with brief explanations
- Recommended resources (books, articles, videos) or practice tasks
- Practice tasks or hands-on exercises

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


def _generate_fallback_plan(topic: str, duration_days: int) -> dict:
    """
    A detailed fallback plan used only when the LLM fails completely.
    Generates unique titles for each day using a rotating list.
    """
    categories = [
        "Introduction and Setup",
        "Core Syntax and Basics",
        "Data Types and Variables",
        "Control Flow and Logic",
        "Functions and Modularity",
        "Data Structures",
        "Object-Oriented Fundamentals",
        "Advanced OOP",
        "Error Handling and Debugging",
        "File and I/O Operations",
        "Libraries and APIs",
        "Performance and Optimization",
        "Testing and Quality Assurance",
        "Project Planning",
        "Final Review and Deployment",
    ]
    subtopics = []
    for i in range(duration_days):
        day_num = i + 1
        cat_idx = i % len(categories)
        title = categories[cat_idx]
        description = (
            f"Comprehensive coverage of {topic} concepts related to {title.lower()}. "
            f"This day includes theory, practical exercises, and real-world applications."
        )
        objectives = [
            f"Understand key principles of {title.lower()}",
            "Apply concepts through hands-on exercises",
            "Build practical skills for real-world scenarios",
        ]
        key_concepts = [
            f"Core {topic} principles",
            "Best practices",
            "Common pitfalls and how to avoid them",
        ]
        resources = [
            f"{topic} documentation and guides",
            "Online tutorials and videos",
            "Practice platforms and coding challenges",
        ]
        practice = [
            f"Complete exercises on {title.lower()}",
            "Review and refactor existing code",
            "Implement a mini-project component",
        ]
        subtopics.append({
            "day": day_num,
            "title": title,
            "description": description,
            "objectives": objectives,
            "key_concepts": key_concepts,
            "resources": resources,
            "practice": practice,
        })
    return {
        "topic": topic,
        "duration_days": duration_days,
        "overview": f"Comprehensive study plan for {topic} over {duration_days} days.",
        "subtopics": subtopics,
    }


def run_planner(topic: str, duration_days: int = 5, context_notes: str = "") -> dict:
    """
    Returns a detailed study plan dict with exactly duration_days days.
    """
    user_content = f"Topic: {topic}\nDuration: {duration_days} days"
    if context_notes:
        # Limit context to avoid hitting the input token limit
        user_content += f"\n\nAdditional context from uploaded materials:\n{context_notes[:3000]}"

    system_prompt = SYSTEM_TEMPLATE.format(duration=duration_days)

    # First attempt with full context and large token budget
    try:
        response = chat(
            messages=[{"role": "user", "content": user_content}],
            system=system_prompt,
            temperature=0.4,
            max_tokens=PLANNER_MAX_TOKENS,
            json_mode=True,
            timeout=PLANNER_TIMEOUT,
        )
        plan = parse_json_response(response)
    except Exception:
        # Retry with minimal context to avoid truncation
        try:
            response = chat(
                messages=[{"role": "user", "content": f"Topic: {topic}\nDuration: {duration_days} days"}],
                system=system_prompt,
                temperature=0.5,
                max_tokens=PLANNER_MAX_TOKENS,
                json_mode=True,
                timeout=PLANNER_TIMEOUT,
            )
            plan = parse_json_response(response)
        except Exception:
            # Final fallback: use the detailed fallback
            plan = _generate_fallback_plan(topic, duration_days)

    # Ensure exactly duration_days subtopics
    if "subtopics" not in plan or not isinstance(plan["subtopics"], list):
        plan["subtopics"] = []

    while len(plan["subtopics"]) < duration_days:
        day_num = len(plan["subtopics"]) + 1
        plan["subtopics"].append({
            "day": day_num,
            "title": f"Day {day_num}: Additional Concepts",
            "description": f"Further exploration of {topic} concepts.",
            "objectives": ["Review core ideas", "Practice applications"],
            "key_concepts": ["Additional concept"],
            "resources": ["Extra resources"],
            "practice": ["Extra practice"],
        })

    if len(plan["subtopics"]) > duration_days:
        plan["subtopics"] = plan["subtopics"][:duration_days]

    # Normalise fields
    for sub in plan["subtopics"]:
        sub.setdefault("day", 0)
        sub.setdefault("title", "Untitled")
        sub.setdefault("description", "Study content.")
        sub.setdefault("objectives", [])
        sub.setdefault("key_concepts", [])
        sub.setdefault("resources", [])
        sub.setdefault("practice", [])

    return plan