"""
utils/guardrails.py — Enterprise‑grade security middleware for Study Buddy AI
Strictly academic‑only filter – blocks all non‑study content.
"""
import re
import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ValidationError, validator

# ────────────────────────────────────────────────────────────────
# 1. PROMPT INJECTION DEFENSE
# ────────────────────────────────────────────────────────────────

INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(?:all\s+)?(previous|prior)\s+(instructions|prompt|context|rules|system)", re.IGNORECASE),
    re.compile(r"(?i)system\s+(?:prompt|override|reset|instruction)", re.IGNORECASE),
    re.compile(r"(?i)you\s+(?:are\s+now\s+)?(?:a\s+)?(?:malicious|evil|hack|terminal|shell|root|admin)", re.IGNORECASE),
    re.compile(r"(?i)(?:act\s+as|pretend\s+to\s+be)\s+(?:a\s+)?(?:system|admin|developer|bot|AI)", re.IGNORECASE),
    re.compile(r"(?i)jailbreak|override\s+security|bypass\s+filter|break\s+out", re.IGNORECASE),
    re.compile(r"(?i)(?:new\s+)?(?:role|persona)\s*[:=]", re.IGNORECASE),
    re.compile(r"(?i)developer\s+mode|debug\s+mode|verbose\s+output", re.IGNORECASE),
    re.compile(r"(?i)show\s+(?:me\s+)?(?:your\s+)?(?:system\s+)?(?:prompt|instructions|configuration)", re.IGNORECASE),
    re.compile(r"(?i)(?:what\s+are\s+)?(?:your\s+)?(?:system\s+)?(?:rules|guidelines|restrictions)", re.IGNORECASE),
    re.compile(r"(?i)expose\s+(?:internal|backend|source\s+code|api\s+key)", re.IGNORECASE),
]

def validate_input_prompt(prompt: str) -> str:
    if not isinstance(prompt, str):
        raise TypeError("Input must be a string")
    normalized = " ".join(prompt.lower().split())
    for pattern in INJECTION_PATTERNS:
        if pattern.search(normalized):
            raise ValueError("Security Violation: Potential Prompt Injection Detected.")
    return prompt

# ────────────────────────────────────────────────────────────────
# 2. PII REDACTION ENGINE
# ────────────────────────────────────────────────────────────────

PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[REDACTED_EMAIL]'),
    (re.compile(r'\b(?:\+?\d{1,3}[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b'), '[REDACTED_PHONE]'),
    (re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'), '[REDACTED_CARD]'),
    (re.compile(r'\b\d{4}\s\d{4}\s\d{4}\s\d{4}\b'), '[REDACTED_CARD]'),
    (re.compile(r'\b\d{12}\b'), '[REDACTED_ID]'),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[REDACTED_SSN]'),
]

def sanitize_pii_data(text: str) -> str:
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern, replacement in PII_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted

# ────────────────────────────────────────────────────────────────
# 3. OUTPUT VALIDATION
# ────────────────────────────────────────────────────────────────

LEAK_PATTERNS = [
    re.compile(r'(?i)(?:system|assistant)\s+(?:prompt|instructions)\s*[:=]'),
    re.compile(r'(?i)(?:internal|backend|api)\s+(?:key|secret|token)'),
    re.compile(r'(?:\\[A-Za-z]:\\|[A-Za-z]:/)'),
    re.compile(r'(?i)(?:file://|/home/|/root/|/etc/)'),
]

def validate_output_response(response: str, max_length: int = 10000) -> str:
    if not isinstance(response, str):
        raise TypeError("Response must be a string")
    if not response.strip():
        raise ValueError("LLM output is empty.")
    if len(response) > max_length:
        raise ValueError(f"Response exceeds maximum allowed length ({max_length} characters).")
    normalized = response.lower()
    for pattern in LEAK_PATTERNS:
        if pattern.search(normalized):
            raise ValueError("Security Alert: Output may contain system instructions or internal file paths.")
    return response

# ────────────────────────────────────────────────────────────────
# 4. STRICT SCHEMA ENFORCEMENT ON TOOL CALLS
# ────────────────────────────────────────────────────────────────

class TavilySearchInput(BaseModel):
    query: str
    max_results: int = 5
    search_depth: str = "basic"
    include_answer: bool = True

    @validator('search_depth')
    def validate_depth(cls, v):
        if v not in ("basic", "advanced"):
            raise ValueError("search_depth must be 'basic' or 'advanced'")
        return v

    @validator('max_results')
    def validate_results(cls, v):
        if not 1 <= v <= 20:
            raise ValueError("max_results must be between 1 and 20")
        return v

class ResearcherInput(BaseModel):
    subtopic: str
    search_query: Optional[str] = None
    document_context: str = ""
    history: Optional[List[Dict[str, str]]] = None

    @validator('subtopic')
    def validate_subtopic(cls, v):
        if not v or not v.strip():
            raise ValueError("subtopic cannot be empty")
        return v.strip()

    @validator('search_query', always=True)
    def validate_search_query(cls, v, values):
        if v is not None and not v.strip():
            return None
        return v

class ToolInputSchema(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]

TOOL_SCHEMAS = {
    "tavily_search": TavilySearchInput,
    "researcher": ResearcherInput,
}

def enforce_tool_schema(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name not in TOOL_SCHEMAS:
        raise ValueError(f"Unknown tool '{tool_name}'. Allowed tools: {list(TOOL_SCHEMAS.keys())}")
    schema = TOOL_SCHEMAS[tool_name]
    try:
        validated = schema(**params)
        return validated.dict()
    except ValidationError as e:
        raise ValueError(f"Security Violation: Tool parameters failed schema validation. Details: {e}")

# ────────────────────────────────────────────────────────────────
# 5. STRICT ACADEMIC‑ONLY FILTER (input + output)
# ────────────────────────────────────────────────────────────────

ACADEMIC_KEYWORDS = {
    # Programming & Web
    "python", "java", "javascript", "html", "css", "sql", "mongodb", "postgresql",
    "react", "angular", "vue", "node", "express", "flask", "django",
    "algorithm", "data structure", "machine learning", "deep learning",
    "langgraph", "langchain", "guardrails", "ai","ml","dl","mistral", "api", "rest", "graphql",
    "docker", "kubernetes", "linux", "unix", "bash", "shell",
    "git", "github", "devops", "ci/cd", "agile", "scrum",
    # Mathematics & Science
    "math", "calculus", "algebra", "linear algebra", "statistics",
    "physics", "chemistry", "biology", "science",
    # Engineering & Tech
    "engineering", "software", "developer", "programming", "coding",
    "cybersecurity", "network", "database", "operating system", "compiler",
    "data science", "artificial intelligence", "robotics", "iot",
    "blockchain", "cloud computing", "web development", "mobile app",
    "game development", "ui/ux", "computer science",
    # Abbreviations & General Study
    "cs", "it", "ece", "eee", "me", "civil", "btech", "bca", "mca",
    "bsc", "msc", "phd", "mtech",
    "college", "university", "school", "education", "academic",
    "study", "learn", "research", "homework", "assignment", "exam", "test",
    "course", "lecture", "tutorial", "class", "subject", "topic", "concept",
    "theory", "practice", "exercise", "solution", "help", "explain", "define",
    "what is", "how does", "compare", "difference",
}


def validate_study_relevance(user_input: str) -> bool:
    if not isinstance(user_input, str):
        raise TypeError("Input must be a string")

    normalized = user_input.lower().strip()
    if not normalized:
        raise ValueError("Empty input is not a valid study query.")

    # Build safe patterns, skip empty keywords
    patterns = []
    for kw in ACADEMIC_KEYWORDS:
        kw = kw.strip()
        if not kw:  # ignore empty strings
            continue
        if ' ' in kw:
            patterns.append(re.escape(kw))
        else:
            patterns.append(r'\b' + re.escape(kw) + r'\b')

    if not patterns:
        raise ValueError("No academic keywords configured.")

    combined = '|'.join(patterns)
    regex = re.compile(combined, re.IGNORECASE)

    if not regex.search(normalized):
        raise ValueError(
            "📚 I'm sorry, but I can only help with study, research, and learning topics. "
            "Please ask a subject-related question."
        )
    return True

def validate_output_study_relevance(output: str) -> bool:
    """
    Strict academic-only filter for OUTPUT:
    - The LLM response itself must contain at least one academic keyword.
    - This prevents non‑study replies even when the original query passed.
    """
    if not isinstance(output, str):
        raise TypeError("Output must be a string")

    normalized = output.lower().strip()
    if not normalized:
        raise ValueError("Empty output is not allowed.")

    has_academic = any(kw in normalized for kw in ACADEMIC_KEYWORDS)

    if not has_academic:
        print(f"Guardrail blocked output: '{output[:200]}...' – no academic keyword found.")
        raise ValueError(
            "📚 I can only share study‑related information. "
            "The response was filtered out."
        )
    return True

# ────────────────────────────────────────────────────────────────
# UTILITY: combined pipeline
# ────────────────────────────────────────────────────────────────

def guard_request(user_input: str) -> str:
    validate_study_relevance(user_input)       # 1. Block non‑academic input
    safe_input = validate_input_prompt(user_input)  # 2. Injection check
    safe_input = sanitize_pii_data(safe_input)      # 3. Redact PII
    return safe_input

def guard_response(llm_output: str) -> str:
    safe_output = validate_output_response(llm_output)       # Length, leaks, emptiness
    validate_output_study_relevance(safe_output)             # NEW: block non‑study output
    return safe_output