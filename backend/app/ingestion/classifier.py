from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import requests

from app.config import settings
from app.ingestion.normalizer import NormalizedDocument

COLLECTIONS = (
    "founder_principles_docs",
    "ai_market_data_docs",
    "startup_examples_docs",
    "technical_constraints_docs",
    "personal_profile_docs",
)

KEYWORD_RULES = {
    "founder_principles_docs": (
        "founder",
        "mission",
        "execution",
        "leadership",
        "go-to-market",
        "strategy",
    ),
    "ai_market_data_docs": (
        "market",
        "pricing",
        "adoption",
        "demand",
        "enterprise",
        "regulation",
    ),
    "startup_examples_docs": (
        "case study",
        "example",
        "startup",
        "wedge",
        "expansion",
        "lessons learned",
    ),
    "technical_constraints_docs": (
        "latency",
        "throughput",
        "architecture",
        "reliability",
        "scalability",
        "cost",
    ),
    "personal_profile_docs": (
        "profile",
        "skills",
        "experience",
        "risk tolerance",
        "background",
        "founder fit",
    ),
}


@dataclass
class ClassificationResult:
    collection: str | None
    confidence: float
    reason: str
    method: str


def _rule_based_classification(title: str, text: str) -> ClassificationResult:
    body = f"{title}\n{text}".lower()
    scores: dict[str, int] = {}
    for collection, keywords in KEYWORD_RULES.items():
        scores[collection] = sum(1 for word in keywords if word in body)

    best_collection = max(scores, key=scores.get)
    best_score = scores[best_collection]
    total = sum(scores.values())
    if total == 0:
        return ClassificationResult(collection=None, confidence=0.0, reason="No rule keywords matched", method="rules")
    confidence = best_score / total if total else 0.0
    reason = f"Matched {best_score} keywords in {best_collection}"
    return ClassificationResult(collection=best_collection, confidence=confidence, reason=reason, method="rules")


def _openrouter_classification(title: str, text: str) -> ClassificationResult | None:
    api_key = settings.open_router_api_key or os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENROUTER_CLASSIFIER_MODEL", "qwen/qwen3.5-397b-a17b")
    prompt = (
        "Classify this document into exactly one collection.\n"
        "Allowed collections: founder_principles_docs, ai_market_data_docs, startup_examples_docs, "
        "technical_constraints_docs, personal_profile_docs.\n"
        "Return strict JSON with keys: collection, confidence, reason.\n"
        "Confidence must be between 0 and 1.\n\n"
        f"Title: {title}\n\n"
        f"Content Preview:\n{text[:6000]}"
    )

    response = None
    for attempt in range(1, 4):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a strict JSON classifier."},
                        {"role": "user", "content": prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                },
                timeout=60,
            )
            response.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if attempt == 3:
                raise
            time.sleep(0.5 * attempt)

    if response is None:
        return None
    content = response.json()["choices"][0]["message"]["content"]
    payload = json.loads(content)
    collection = payload.get("collection")
    confidence = float(payload.get("confidence", 0))
    reason = str(payload.get("reason", ""))
    if collection not in COLLECTIONS:
        return None
    confidence = max(0.0, min(1.0, confidence))
    return ClassificationResult(collection=collection, confidence=confidence, reason=reason, method="openrouter")


def classify_document(
    normalized_doc: NormalizedDocument,
    *,
    llm_threshold: float = 0.55,
    allow_llm: bool = True,
) -> ClassificationResult:
    preview_text = normalized_doc.normalized_text
    rule_result = _rule_based_classification(normalized_doc.title, preview_text)
    if not allow_llm:
        return rule_result
    if rule_result.confidence >= llm_threshold and rule_result.collection is not None:
        return rule_result

    try:
        llm_result = _openrouter_classification(normalized_doc.title, preview_text)
    except requests.exceptions.RequestException:
        return ClassificationResult(
            collection=rule_result.collection,
            confidence=rule_result.confidence,
            reason=f"{rule_result.reason}; llm unavailable",
            method=rule_result.method,
        )
    except Exception:
        return ClassificationResult(
            collection=rule_result.collection,
            confidence=rule_result.confidence,
            reason=f"{rule_result.reason}; llm unavailable",
            method=rule_result.method,
        )

    if llm_result is None:
        return rule_result
    return llm_result
