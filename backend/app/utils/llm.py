from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _fallback_structured_idea(idea_description: str, target_customer: str | None, problem_statement: str | None) -> dict[str, Any]:
    return {
        "customer": target_customer or "Unknown",
        "problem": problem_statement or "Not explicitly provided",
        "solution": idea_description[:400],
        "technical_core": "To be inferred",
        "classification": {
            "market_type": "Unknown",
            "startup_type": "Unknown",
        },
    }


def _fallback_critic_result(evidence_count: int) -> dict[str, Any]:
    base = 65 if evidence_count >= 20 else 55 if evidence_count >= 10 else 45
    result = {
        "dimensions": {
            "market": {"score": base, "rationale": "Fallback estimate due to model unavailability."},
            "technical": {"score": min(100, base + 3), "rationale": "Fallback estimate due to model unavailability."},
            "distribution": {"score": max(0, base - 5), "rationale": "Fallback estimate due to model unavailability."},
            "founder_fit": {"score": base, "rationale": "Fallback estimate due to model unavailability."},
            "timing": {"score": max(0, base - 2), "rationale": "Fallback estimate due to model unavailability."},
        },
        "top_risks": [
            "Limited confidence in generated assessment",
            "Evidence coverage may be insufficient",
            "Further validation interviews required",
        ],
        "low_confidence": evidence_count < 20,
    }
    return result


def call_openrouter_json(system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
    api_key = settings.open_router_api_key
    if not api_key:
        return None

    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=40)
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        return _extract_json_object(content)
    except Exception:
        return None


def extract_structured_idea(idea_description: str, target_customer: str | None, problem_statement: str | None) -> dict[str, Any]:
    system_prompt = (
        "You extract startup idea structure. Return strict JSON with keys: "
        "customer, problem, solution, technical_core, classification."
    )
    user_prompt = json.dumps(
        {
            "idea_description": idea_description,
            "target_customer": target_customer,
            "problem_statement": problem_statement,
        }
    )
    parsed = call_openrouter_json(system_prompt, user_prompt)
    if isinstance(parsed, dict):
        return parsed
    return _fallback_structured_idea(idea_description, target_customer, problem_statement)


def evaluate_with_critic(
    structured_idea: dict[str, Any],
    profile_data: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    system_prompt = (
        "You are a skeptical startup evaluator. Score exactly 5 dimensions: "
        "market, technical, distribution, founder_fit, timing. Return JSON with keys: "
        "dimensions, top_risks, low_confidence."
    )
    user_prompt = json.dumps(
        {
            "structured_idea": structured_idea,
            "profile_data": profile_data,
            "retrieved_chunks": retrieved_chunks[:30],
        }
    )
    parsed = call_openrouter_json(system_prompt, user_prompt)
    if isinstance(parsed, dict):
        return parsed
    return _fallback_critic_result(len(retrieved_chunks))

