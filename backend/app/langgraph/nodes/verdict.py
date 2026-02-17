from __future__ import annotations

from typing import Any

from ..state import EvaluationState


COLLECTION_DIMENSION_HINTS: dict[str, list[str]] = {
    "founder_principles": ["founder_fit", "distribution"],
    "ai_market_data": ["market", "timing"],
    "startup_examples": ["distribution", "market"],
    "technical_constraints": ["technical", "timing"],
    "personal_profile": ["founder_fit"],
}


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _source_reason(collection: str, retrieval_reason: str | None, title: str) -> str:
    default_reason = {
        "founder_principles": "Used to evaluate founder execution patterns and operating principles.",
        "ai_market_data": "Used to evaluate market demand, competition, and adoption conditions.",
        "startup_examples": "Used to compare against analogous startup patterns and outcomes.",
        "technical_constraints": "Used to assess engineering feasibility, reliability, and scaling constraints.",
        "personal_profile": "Used to assess founder-background fit and execution capacity.",
    }.get(collection, "Used as supporting context for the evaluation.")
    reason = retrieval_reason or default_reason
    return f"{reason} Source: {title}."


def _build_evidence_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    seen_title_collection: set[tuple[str, str]] = set()

    for chunk in chunks:
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        collection = _clean_text(chunk.get("collection")) or "unknown"
        chunk_id = _clean_text(chunk.get("id"))
        title = (
            _clean_text(chunk.get("title"))
            or _clean_text(metadata.get("title"))
            or _clean_text(metadata.get("document_title"))
            or _clean_text(metadata.get("doc_name"))
            or (f"Chunk {chunk_id}" if chunk_id else "Untitled source")
        )

        if chunk_id and chunk_id in seen_chunk_ids:
            continue
        title_key = (collection, title.lower())
        if title_key in seen_title_collection:
            continue

        if chunk_id:
            seen_chunk_ids.add(chunk_id)
        seen_title_collection.add(title_key)

        source_url = (
            _clean_text(metadata.get("source_url"))
            or _clean_text(metadata.get("url"))
            or _clean_text(metadata.get("link"))
        )
        source_name = (
            _clean_text(metadata.get("source_name"))
            or _clean_text(metadata.get("publisher"))
            or _clean_text(chunk.get("source"))
        )
        snippet = _clean_text(chunk.get("content"))
        if snippet and len(snippet) > 220:
            snippet = f"{snippet[:220].rstrip()}..."
        retrieval_reason = _clean_text(chunk.get("retrieval_reason")) or _clean_text(metadata.get("retrieval_reason"))
        dimension_hints = COLLECTION_DIMENSION_HINTS.get(collection, [])

        sources.append(
            {
                "chunk_id": chunk_id,
                "title": title,
                "collection": collection,
                "source_name": source_name,
                "source_url": source_url,
                "snippet": snippet,
                "retrieval_method": _clean_text(chunk.get("retrieval_method")),
                "supporting_dimensions": dimension_hints,
                "why_relevant": _source_reason(collection, retrieval_reason, title),
            }
        )

    return sources[:20]


def verdict_node(state: EvaluationState) -> EvaluationState:
    scores = state.get("dimension_scores", {})
    available = [value for value in scores.values() if isinstance(value, int)]
    overall = int(round(sum(available) / len(available))) if available else None

    if overall is None:
        verdict = None
    elif overall >= 70:
        verdict = "GO"
    elif overall >= 55:
        verdict = "CONDITIONAL"
    else:
        verdict = "NO-GO"

    evidence_sources = _build_evidence_sources(state.get("retrieved_chunks", []))

    return {
        "overall_score": overall,
        "verdict": verdict,
        "evidence_sources": evidence_sources,
    }
