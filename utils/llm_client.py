"""
utils/llm_client.py — Mistral REST API client with JSON mode support
"""
from __future__ import annotations
import json
import re
import requests
from typing import List, Dict, Any, Optional
from config import MISTRAL_API_KEY, MISTRAL_MODEL

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

def chat(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    json_mode: bool = False,
) -> str:
    """
    Send a chat completion request to Mistral.
    If json_mode is True, we add a system instruction and set response_format.
    """
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not set. Please add it to your .env file.")

    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    payload = {
        "model": MISTRAL_MODEL,
        "messages": full_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(MISTRAL_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Mistral API error: {e}") from e

def parse_json_response(text: str) -> Dict[str, Any]:
    """
    Attempt to extract JSON from a string that may contain markdown fences,
    extra text, or be malformed. Tries to fix common issues.
    """
    # 1. Remove markdown code fences
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        # If no fences, try to find the first '{' and last '}'
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and start < end:
            text = text[start:end+1]

    # 2. Remove trailing commas before closing braces/brackets (common JSON error)
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # 3. Try to parse
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # 4. If still fails, attempt to repair by truncating at the last valid brace
        #    Find all positions of '{' and '}' and try to extract a valid JSON prefix
        stack = []
        valid_end = -1
        for i, ch in enumerate(text):
            if ch == '{':
                stack.append(i)
            elif ch == '}':
                if stack:
                    stack.pop()
                    if not stack:  # we closed the root object
                        valid_end = i + 1
        if valid_end != -1:
            candidate = text[:valid_end]
            try:
                return json.loads(candidate)
            except:
                pass

        # 5. Last resort: return a minimal fallback
        raise ValueError(f"Could not parse JSON from response. Error: {e}. Response snippet: {text[:200]}...")