"""
utils/llm_client.py — Mistral REST API client with robust timeout & error handling.
All output still passes through guard_response for safety.
"""
from __future__ import annotations
import json
import re
import base64
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import MISTRAL_API_KEY, MISTRAL_MODEL

# Guardrails for output only (input is already guarded in chat_agent)
from utils.guardrails import guard_response, sanitize_pii_data

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
VISION_MODEL = "pixtral-12b-2409"


def chat(
    messages: List[Dict[str, str]],
    system: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    json_mode: bool = False,
    timeout: int = 30,          # shorter total timeout
) -> str:
    """
    Send a chat completion request to Mistral.
    Only applies output guard (guard_response) – input guarding is done upstream.
    """
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set.")

    # Build payload (no input guard – assume already safe)
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": sanitize_pii_data(system)})
    full_messages.extend(messages)   # messages are already clean

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

    # ─── REQUEST with strict timeouts ──────────────────────────────────
    try:
        response = requests.post(
            MISTRAL_API_URL,
            json=payload,
            headers=headers,
            timeout=(10, timeout),   # (connect timeout, read timeout)
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not content or content.strip() == "":
            raise RuntimeError("Mistral returned an empty response.")
        # Output guard
        return guard_response(content)
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Request to Mistral timed out after {timeout}s.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Failed to connect to Mistral API. Check your network or API endpoint.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Mistral API request failed: {e}") from e
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Unexpected API response format: {e}") from e


def parse_json_response(text: str) -> Dict[str, Any]:
    # (unchanged – your existing parser)
    if not text or not text.strip():
        raise ValueError("Empty text passed to parse_json_response")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start:i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        repaired = re.sub(r',\s*}', '}', candidate)
                        repaired = re.sub(r',\s*]', ']', repaired)
                        try:
                            parsed = json.loads(repaired)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError:
                            pass
                    break
    raise ValueError(f"Could not parse valid JSON from response: {cleaned[:300]}")


def vision_chat(image_path: str, prompt: str = "Describe this image in detail.") -> str:
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set.")
    image_file = Path(image_path)
    if not image_file.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    with open(image_file, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    ext = image_file.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/{mime};base64,{b64_data}"},
                ],
            }
        ],
        "max_tokens": 1500,
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(MISTRAL_API_URL, json=payload, headers=headers, timeout=(10, 60))
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise RuntimeError("Mistral vision returned an empty response.")
        return guard_response(content)
    except requests.exceptions.Timeout:
        raise RuntimeError("Vision request timed out.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Mistral vision API request failed: {e}") from e
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Unexpected vision API response format: {e}") from e