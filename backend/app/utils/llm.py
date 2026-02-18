from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from app.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3.5-397b-a17b")
KNOWN_IDEA_TAGS = [
    "b2b",
    "b2c",
    "ai agent",
    "fintech",
    "healthtech",
    "edtech",
    "devtools",
    "saas",
    "marketplace",
    "infra",
    "cybersecurity",
    "data",
    "automation",
    "sales",
    "revenue ops",
]


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


def _fallback_idea_title(idea_description: str) -> str:
    words = [token for token in re.split(r"[^A-Za-z0-9]+", idea_description) if token]
    if not words:
        return "Untitled Startup Idea"
    normalized = " ".join(words[:8]).strip()
    return normalized[:64] if normalized else "Untitled Startup Idea"


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


def generate_idea_title(idea_description: str, target_customer: str | None, problem_statement: str | None) -> str:
    system_prompt = (
        "You generate concise startup idea titles. "
        "Return strict JSON with key 'title'. Keep it 3-7 words and avoid quotes."
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
        raw_title = parsed.get("title")
        if isinstance(raw_title, str):
            candidate = " ".join(raw_title.strip().split())
            if candidate:
                return candidate[:80]
    return _fallback_idea_title(idea_description)


def generate_idea_categorization(
    idea_description: str,
    target_customer: str | None,
    problem_statement: str | None,
    startup_type: str | None,
    market_type: str | None,
) -> dict[str, str]:
    system_prompt = (
        "You categorize startup ideas. Return strict JSON with keys: "
        "type, market, target, main_competitor, trend_analysis. "
        "Keep values concise and specific."
    )
    user_prompt = json.dumps(
        {
            "idea_description": idea_description,
            "target_customer": target_customer,
            "problem_statement": problem_statement,
            "startup_type": startup_type,
            "market_type": market_type,
        }
    )
    parsed = call_openrouter_json(system_prompt, user_prompt)
    defaults = {
        "type": startup_type or "Not specified",
        "market": market_type or "Not specified",
        "target": target_customer or "Not specified",
        "main_competitor": "Not specified",
        "trend_analysis": "Not specified",
    }
    if not isinstance(parsed, dict):
        return defaults

    result = dict(defaults)
    for key in result:
        value = parsed.get(key)
        if isinstance(value, str):
            cleaned = " ".join(value.strip().split())
            if cleaned:
                result[key] = cleaned[:320]
    return result


def evaluate_with_critic(
    structured_idea: dict[str, Any],
    profile_data: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
    dimension_evidence_map: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    def compact_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        content = str(chunk.get("content") or "").replace("\n", " ").strip()
        return {
            "id": chunk.get("id"),
            "collection": chunk.get("collection"),
            "title": chunk.get("title") or metadata.get("title"),
            "source": chunk.get("source") or metadata.get("source"),
            "source_url": metadata.get("source_url"),
            "retrieval_method": chunk.get("retrieval_method"),
            "content_excerpt": content[:320],
        }

    compact_retrieved = [compact_chunk(chunk) for chunk in retrieved_chunks[:40] if isinstance(chunk, dict)]
    compact_dimension_map = {
        key: [compact_chunk(chunk) for chunk in value[:8] if isinstance(chunk, dict)]
        for key, value in (dimension_evidence_map or {}).items()
        if isinstance(value, list)
    }

    system_prompt = (
        "You are a skeptical startup evaluator. Score exactly 5 dimensions: "
        "market, technical, distribution, founder_fit, timing. Return JSON with keys: "
        "dimensions, top_risks, low_confidence. Use both internal and web evidence when available. "
        "Prefer recent, concrete external evidence for market/timing claims and avoid hallucinated facts."
    )
    user_prompt = json.dumps(
        {
            "structured_idea": structured_idea,
            "profile_data": profile_data,
            "retrieved_chunks": compact_retrieved,
            "dimension_evidence_map": compact_dimension_map,
        }
    )
    parsed = call_openrouter_json(system_prompt, user_prompt)
    if isinstance(parsed, dict):
        return parsed
    return _fallback_critic_result(len(retrieved_chunks))


def generate_explanatory_summaries(
    idea_title: str,
    idea_description: str,
    dimension_scores: dict[str, int | None],
    dimension_analyses: dict[str, dict[str, Any]],
    top_risks: list[str] | None,
    evidence_mix: dict[str, Any] | None,
    profile_data: dict[str, Any] | None,
    verdict: str | None,
    overall_score: int | None,
) -> dict[str, str] | None:
    system_prompt = (
        "You are writing investor-grade evaluation explanations.\n"
        "Return strict JSON with keys: idea_summary, founder_fit_summary.\n"
        "Requirements:\n"
        "- Explain WHY the verdict was reached using cause-and-effect logic.\n"
        "- Mention concrete strengths, constraints, and tradeoffs.\n"
        "- Do not list raw sources or document IDs.\n"
        "- Be specific, skeptical, and practical.\n"
        "- idea_summary should focus on market/product/distribution/timing.\n"
        "- founder_fit_summary should focus on founder capabilities, execution risk, and GTM credibility.\n"
        "- Keep each summary to one dense paragraph."
    )
    user_prompt = json.dumps(
        {
            "idea_title": idea_title,
            "idea_description": idea_description,
            "verdict": verdict,
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "dimension_analyses": dimension_analyses,
            "top_risks": top_risks or [],
            "evidence_mix": evidence_mix or {},
            "profile_data": profile_data or {},
        }
    )
    parsed = call_openrouter_json(system_prompt, user_prompt)
    if not isinstance(parsed, dict):
        return None
    idea_summary = parsed.get("idea_summary")
    founder_fit_summary = parsed.get("founder_fit_summary")
    if not isinstance(idea_summary, str) or not idea_summary.strip():
        return None
    if not isinstance(founder_fit_summary, str) or not founder_fit_summary.strip():
        return None
    return {
        "idea_summary": " ".join(idea_summary.strip().split()),
        "founder_fit_summary": " ".join(founder_fit_summary.strip().split()),
    }


def generate_dimension_narratives(
    *,
    structured_idea: dict[str, Any],
    profile_data: dict[str, Any],
    dimension_scores: dict[str, int | None],
    dimension_analyses: dict[str, dict[str, Any]],
    top_risks: list[str] | None,
    dimension_evidence_map: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, dict[str, str]] | None:
    def _compact_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        content = str(chunk.get("content") or "").replace("\n", " ").strip()
        return {
            "collection": chunk.get("collection"),
            "title": chunk.get("title") or metadata.get("title"),
            "source": chunk.get("source") or metadata.get("source"),
            "source_url": metadata.get("source_url"),
            "content_excerpt": content[:240],
        }

    compact_evidence_map = {
        key: [_compact_chunk(chunk) for chunk in value[:5] if isinstance(chunk, dict)]
        for key, value in (dimension_evidence_map or {}).items()
        if isinstance(value, list)
    }

    system_prompt = (
        "You rewrite startup evaluation dimension output for founders.\n"
        "Return strict JSON with keys: market, technical, distribution, founder_fit, timing.\n"
        "Each dimension value must be an object with keys:\n"
        "- rationale: one concise paragraph (2-4 sentences), specific, no document IDs, no raw source dumps.\n"
        "- improvement: 1-2 sentences with concrete changes to improve this dimension.\n"
        "Rules:\n"
        "- Keep the original score meaning; do not change scores.\n"
        "- Be skeptical and actionable.\n"
        "- Mention competition and differentiation where relevant.\n"
        "- For market, include niche focus + positioning advice when useful.\n"
    )
    user_prompt = json.dumps(
        {
            "structured_idea": structured_idea,
            "profile_data": profile_data,
            "dimension_scores": dimension_scores,
            "dimension_analyses": dimension_analyses,
            "top_risks": top_risks or [],
            "dimension_evidence_map": compact_evidence_map,
        }
    )
    parsed = call_openrouter_json(system_prompt, user_prompt)
    if not isinstance(parsed, dict):
        return None

    result: dict[str, dict[str, str]] = {}
    for dimension in ("market", "technical", "distribution", "founder_fit", "timing"):
        payload = parsed.get(dimension)
        if not isinstance(payload, dict):
            continue
        rationale = payload.get("rationale")
        improvement = payload.get("improvement")
        if not isinstance(rationale, str) or not rationale.strip():
            continue
        if not isinstance(improvement, str) or not improvement.strip():
            continue
        result[dimension] = {
            "rationale": " ".join(rationale.strip().split()),
            "improvement": " ".join(improvement.strip().split()),
        }

    return result or None


def _heuristic_tags(text: str, allow_default: bool = True) -> tuple[list[str], str | None]:
    lowered = text.lower()
    tags: list[str] = []
    mapping = {
        "b2b": ["b2b", "enterprise", "smb", "sales team", "revops"],
        "b2c": ["b2c", "consumer"],
        "ai agent": ["ai agent", "agentic", "copilot", "assistant"],
        "fintech": ["fintech", "payments", "bank", "lending", "compliance"],
        "healthtech": ["healthtech", "health", "clinic", "ehr", "patient"],
        "edtech": ["edtech", "learning", "education", "school"],
        "devtools": ["developer", "devtool", "sdk", "api platform"],
        "saas": ["saas", "subscription"],
        "marketplace": ["marketplace", "buyers and sellers"],
        "infra": ["infrastructure", "infra", "platform"],
        "cybersecurity": ["security", "cyber", "threat", "identity"],
        "data": ["data", "analytics", "warehouse", "etl"],
        "automation": ["automation", "workflow", "orchestration"],
        "sales": ["sales", "crm", "pipeline", "prospecting"],
        "revenue ops": ["revops", "revenue operations", "forecasting"],
    }
    for tag, keys in mapping.items():
        if any(key in lowered for key in keys):
            tags.append(tag)
    if not tags and allow_default:
        tags = ["saas"]
    folder = "General"
    if "fintech" in tags:
        folder = "Fintech"
    elif "healthtech" in tags:
        folder = "Healthtech"
    elif "edtech" in tags:
        folder = "Edtech"
    elif "ai agent" in tags:
        folder = "AI Agents"
    elif "devtools" in tags:
        folder = "Developer Tools"
    elif "b2b" in tags:
        folder = "B2B"
    elif "b2c" in tags:
        folder = "B2C"
    if not tags:
        return [], None
    return tags[:6], folder


def generate_idea_tags(
    idea_description: str,
    target_customer: str | None,
    problem_statement: str | None,
    startup_type: str | None,
    market_type: str | None,
) -> tuple[list[str], str | None]:
    payload = {
        "idea_description": idea_description,
        "target_customer": target_customer,
        "problem_statement": problem_statement,
        "startup_type": startup_type,
        "market_type": market_type,
        "known_tags": KNOWN_IDEA_TAGS,
    }
    system_prompt = (
        "You assign startup idea tags for filtering. Return strict JSON with keys: tags (array), folder (string).\n"
        "Rules: choose 2-6 tags from known_tags when possible; keep tags lowercase and concise; "
        "folder should be a short category label like B2B, AI Agents, Fintech, DevTools, Healthtech."
    )
    parsed = call_openrouter_json(system_prompt, json.dumps(payload))
    if isinstance(parsed, dict):
        raw_tags = parsed.get("tags")
        raw_folder = parsed.get("folder")
        tags: list[str] = []
        if isinstance(raw_tags, list):
            for tag in raw_tags:
                if isinstance(tag, str):
                    normalized = " ".join(tag.strip().lower().split())
                    if normalized and normalized not in tags:
                        tags.append(normalized)
        folder = " ".join(raw_folder.strip().split()) if isinstance(raw_folder, str) and raw_folder.strip() else None
        if tags:
            return tags[:6], folder

    combined = " ".join(
        [
            idea_description or "",
            target_customer or "",
            problem_statement or "",
            startup_type or "",
            market_type or "",
        ]
    )
    return _heuristic_tags(combined)


def parse_filter_tags(filter_query: str) -> tuple[list[str], str | None]:
    query = " ".join(filter_query.split()).strip()
    if not query:
        return [], None
    system_prompt = (
        "You map user filter text to startup tags and optional folder. Return strict JSON with keys: tags (array), folder (string|null). "
        "Tags must be lowercase concise labels."
    )
    parsed = call_openrouter_json(system_prompt, json.dumps({"query": query, "known_tags": KNOWN_IDEA_TAGS}))
    if isinstance(parsed, dict):
        tags: list[str] = []
        raw_tags = parsed.get("tags")
        if isinstance(raw_tags, list):
            for tag in raw_tags:
                if isinstance(tag, str):
                    normalized = " ".join(tag.strip().lower().split())
                    if normalized and normalized not in tags:
                        tags.append(normalized)
        raw_folder = parsed.get("folder")
        folder = " ".join(raw_folder.strip().split()) if isinstance(raw_folder, str) and raw_folder.strip() else None
        if tags or folder:
            return tags[:6], folder
    return _heuristic_tags(query, allow_default=False)


def generate_search_keywords(
    idea_description: str,
    target_customer: str | None,
    problem_statement: str | None,
    startup_type: str | None,
    market_type: str | None,
) -> list[str]:
    stopwords = {
        "for",
        "with",
        "and",
        "the",
        "from",
        "into",
        "using",
        "based",
        "automated",
        "automation",
        "solution",
        "software",
        "platform",
        "tool",
        "app",
        "services",
    }

    def clean_keyword(value: str) -> str | None:
        cleaned = " ".join(value.strip().lower().split())
        if not cleaned:
            return None
        # Remove date-like fragments and non-commercial tails.
        cleaned = re.sub(r"\b(19|20)\d{2}\b", "", cleaned)
        cleaned = re.sub(r"\b(q[1-4]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", "", cleaned)
        cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
        cleaned = " ".join(cleaned.split()).strip()
        tokens = [token for token in cleaned.split() if token and token not in stopwords]
        if len(tokens) > 2:
            tokens = tokens[:2]
        cleaned = " ".join(tokens).strip()
        if len(cleaned) < 4:
            return None
        return cleaned

    def fallback_templates() -> list[str]:
        market = (market_type or "").strip().lower()
        segment = (target_customer or "").strip().lower()
        problem = (problem_statement or "").strip().lower()
        startup = (startup_type or "").strip().lower()
        templates = [
            f"{segment} {problem} solution" if segment and problem else "",
            f"{segment} {startup} app" if segment and startup else "",
            f"{market} {startup} software" if market and startup else "",
            f"{segment} pricing" if segment else "",
            f"{startup} alternatives" if startup else "",
            f"{problem} software" if problem else "",
        ]
        cleaned_templates: list[str] = []
        for template in templates:
            keyword = clean_keyword(template)
            if keyword and keyword not in cleaned_templates:
                cleaned_templates.append(keyword)
        return cleaned_templates[:4]

    payload = {
        "idea_description": idea_description,
        "target_customer": target_customer,
        "problem_statement": problem_statement,
        "startup_type": startup_type,
        "market_type": market_type,
    }
    system_prompt = (
        "You generate high-intent Google search keywords for startup demand validation.\n"
        "Return strict JSON with key: keywords (array of strings).\n"
        "Rules:\n"
        "- Return 3 to 4 concise keywords.\n"
        "- Each keyword must be 1-2 words and commercially-intent focused.\n"
        "- Use phrases users actually search for when evaluating products.\n"
        "- Avoid generic terms and remove dates/years/time ranges.\n"
        "- Prefer product category + core use-case terms."
    )
    parsed = call_openrouter_json(system_prompt, json.dumps(payload))
    if isinstance(parsed, dict):
        raw_keywords = parsed.get("keywords")
        if isinstance(raw_keywords, list):
            cleaned: list[str] = []
            for item in raw_keywords:
                if not isinstance(item, str):
                    continue
                value = clean_keyword(item)
                if value and value not in cleaned:
                    cleaned.append(value)
            if cleaned:
                return cleaned[:4]

    templates = fallback_templates()
    if templates:
        return templates

    blob = " ".join(
        value for value in [idea_description[:220], target_customer or "", problem_statement or "", startup_type or ""] if value
    ).lower()
    words = [token for token in re.split(r"[^a-z0-9]+", blob) if len(token) > 3]
    candidates: list[str] = []
    for idx in range(0, max(0, len(words) - 1)):
        phrase = clean_keyword(" ".join(words[idx : idx + 2]))
        if phrase and phrase not in candidates:
            candidates.append(phrase)
        if len(candidates) >= 4:
            break
    return candidates[:4]
