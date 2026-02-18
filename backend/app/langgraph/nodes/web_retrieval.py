from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.web_search_service import web_search

from ..state import EvaluationState

DIMENSION_ORDER = ("market", "technical", "distribution", "founder_fit", "timing")
DIMENSION_MIX_RULES: dict[str, list[tuple[str, int]]] = {
    "market": [("ai_market_data", 3), ("web", 3), ("startup_examples", 2)],
    "technical": [("technical_constraints", 4), ("web", 2), ("founder_principles", 1)],
    "distribution": [("startup_examples", 3), ("founder_principles", 1), ("web", 3), ("ai_market_data", 1)],
    "founder_fit": [("personal_profile", 2), ("founder_principles", 3), ("web", 2)],
    "timing": [("ai_market_data", 3), ("web", 3), ("technical_constraints", 2)],
}
DIMENSION_TARGET = 7


def _build_web_queries(state: EvaluationState) -> list[str]:
    idea = state.get("idea_description", "")
    target = state.get("target_customer") or ""
    problem = state.get("problem_statement") or ""
    startup_type = state.get("startup_type") or ""
    market_type = state.get("market_type") or ""

    compact_idea = " ".join(idea.split())[:120]
    compact_problem = " ".join(problem.split())[:90]
    compact_target = " ".join(target.split())[:70]
    compact_type = " ".join([startup_type, market_type]).strip()

    primary = " ".join(part for part in [compact_idea, compact_target, compact_problem] if part).strip()
    market_context = " ".join(part for part in [compact_type, compact_target, "market demand competition"] if part).strip()
    go_to_market = " ".join(part for part in [compact_idea, "distribution channels pricing"] if part).strip()

    candidates = [primary, market_context, go_to_market]
    queries: list[str] = []
    for candidate in candidates:
        normalized = " ".join(candidate.split()).strip()
        if normalized and normalized not in queries:
            queries.append(normalized[:180])
    return queries[: max(1, settings.web_search_query_limit_per_eval)]


def _normalize_collection(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.endswith("_docs"):
        text = text[: -len("_docs")]
    return text


def _chunk_source_key(chunk: dict[str, Any]) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    candidates = [
        metadata.get("doc_id"),
        metadata.get("document_id"),
        metadata.get("source_url"),
        chunk.get("id"),
        metadata.get("source"),
        metadata.get("title"),
        chunk.get("title"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip().lower()
    return f"unknown::{_normalize_collection(chunk.get('collection'))}"


def _chunk_rank(chunk: dict[str, Any], index: int) -> int:
    method = str(chunk.get("retrieval_method") or "").strip().lower()
    method_bonus = 0
    if method == "vector":
        method_bonus = 6
    elif method == "keyword":
        method_bonus = 3
    elif method == "web_search":
        method_bonus = 2
    return max(0, 200 - index) + method_bonus


def _select_dimension_chunks(
    dimension: str,
    chunks: list[dict[str, Any]],
    reuse_counts: dict[str, int],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_source_keys: set[str] = set()
    ranked = sorted(
        (
            (chunk, _normalize_collection(chunk.get("collection")), _chunk_source_key(chunk), _chunk_rank(chunk, idx))
            for idx, chunk in enumerate(chunks)
        ),
        key=lambda item: item[3],
        reverse=True,
    )

    def try_add(candidate_chunk: dict[str, Any], source_key: str, base_rank: int) -> bool:
        if source_key in selected_source_keys:
            return False
        # Penalize source reuse across dimensions so one doc does not dominate.
        effective_rank = base_rank - (reuse_counts.get(source_key, 0) * 25)
        if effective_rank < 0:
            return False
        selected.append(candidate_chunk)
        selected_source_keys.add(source_key)
        reuse_counts[source_key] = reuse_counts.get(source_key, 0) + 1
        return True

    rules = DIMENSION_MIX_RULES.get(dimension, [])
    for collection, quota in rules:
        if len(selected) >= DIMENSION_TARGET:
            break
        remaining = max(0, min(quota, DIMENSION_TARGET - len(selected)))
        if remaining == 0:
            continue
        for chunk, chunk_collection, source_key, rank in ranked:
            if chunk_collection != collection:
                continue
            if try_add(chunk, source_key, rank):
                remaining -= 1
            if remaining == 0 or len(selected) >= DIMENSION_TARGET:
                break

    if len(selected) < DIMENSION_TARGET:
        for chunk, _chunk_collection, source_key, rank in ranked:
            if len(selected) >= DIMENSION_TARGET:
                break
            try_add(chunk, source_key, rank)

    return selected


def _build_dimension_evidence_map(chunks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    reuse_counts: dict[str, int] = {}
    evidence_map: dict[str, list[dict[str, Any]]] = {}
    for dimension in DIMENSION_ORDER:
        evidence_map[dimension] = _select_dimension_chunks(dimension=dimension, chunks=chunks, reuse_counts=reuse_counts)
    return evidence_map


def _count_cross_dimension_reuse(evidence_map: dict[str, list[dict[str, Any]]]) -> int:
    counts: dict[str, int] = {}
    for scoped_chunks in evidence_map.values():
        for chunk in scoped_chunks:
            key = _chunk_source_key(chunk)
            counts[key] = counts.get(key, 0) + 1
    return sum(1 for value in counts.values() if value > 1)


def _dimension_coverage_low_confidence(evidence_map: dict[str, list[dict[str, Any]]], diversified_chunks: list[dict[str, Any]]) -> bool:
    if len(diversified_chunks) < 10:
        return True
    if not evidence_map:
        return True
    per_dimension_counts = [len(chunks) for chunks in evidence_map.values()]
    if not per_dimension_counts:
        return True
    # Require at least 3 sources per dimension for acceptable confidence.
    return min(per_dimension_counts) < 3


def _flatten_dimension_evidence_map(evidence_map: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for dimension in DIMENSION_ORDER:
        for chunk in evidence_map.get(dimension, []):
            chunk_id = str(chunk.get("id") or "").strip()
            key = chunk_id or _chunk_source_key(chunk)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            ordered.append(chunk)
    return ordered


def web_retrieval_node(state: EvaluationState) -> EvaluationState:
    internal_chunks = state.get("retrieved_chunks", [])
    if not isinstance(internal_chunks, list):
        internal_chunks = []
    should_run_web = bool(state.get("web_enabled", True))
    raw_diagnostics = state.get("parse_diagnostics", [])
    parse_diagnostics = list(raw_diagnostics) if isinstance(raw_diagnostics, list) else []

    if not should_run_web:
        evidence_map = _build_dimension_evidence_map(internal_chunks)
        diversified_chunks = _flatten_dimension_evidence_map(evidence_map)
        parse_diagnostics.append(f"cross_dimension_reused_sources:{_count_cross_dimension_reuse(evidence_map)}")
        low_confidence = _dimension_coverage_low_confidence(evidence_map, diversified_chunks)
        return {
            "internal_retrieved_chunks": internal_chunks,
            "web_retrieved_chunks": [],
            "web_queries_used": [],
            "dimension_evidence_map": evidence_map,
            "retrieved_chunks": diversified_chunks,
            "parse_diagnostics": parse_diagnostics,
            "low_confidence": low_confidence,
        }

    # Budget safeguard: if internal coverage is already strong, skip web calls entirely.
    internal_evidence_map = _build_dimension_evidence_map(internal_chunks)
    internal_diversified = _flatten_dimension_evidence_map(internal_evidence_map)
    if not _dimension_coverage_low_confidence(internal_evidence_map, internal_diversified):
        parse_diagnostics.append("web_search_skipped:internal_coverage_sufficient")
        parse_diagnostics.append(f"cross_dimension_reused_sources:{_count_cross_dimension_reuse(internal_evidence_map)}")
        return {
            "internal_retrieved_chunks": internal_chunks,
            "web_retrieved_chunks": [],
            "web_queries_used": [],
            "dimension_evidence_map": internal_evidence_map,
            "retrieved_chunks": internal_diversified,
            "parse_diagnostics": parse_diagnostics,
            "low_confidence": False,
        }

    queries = _build_web_queries(state)
    web_chunks: list[dict] = []
    seen_ids: set[str] = set()
    max_web_chunks = max(1, settings.web_search_max_chunks_per_eval)
    for query in queries:
        if len(web_chunks) >= max_web_chunks:
            break
        remaining = max_web_chunks - len(web_chunks)
        per_query_limit = min(max(2, settings.web_search_max_results), remaining)
        for chunk in web_search(query, max_results=per_query_limit):
            key = str(chunk.get("id") or "")
            if key and key in seen_ids:
                continue
            if key:
                seen_ids.add(key)
            web_chunks.append(chunk)
            if len(web_chunks) >= max_web_chunks:
                break

    merged = [*internal_chunks, *web_chunks]
    evidence_map = _build_dimension_evidence_map(merged)
    diversified_chunks = _flatten_dimension_evidence_map(evidence_map)
    parse_diagnostics.append(f"cross_dimension_reused_sources:{_count_cross_dimension_reuse(evidence_map)}")
    low_confidence = _dimension_coverage_low_confidence(evidence_map, diversified_chunks)
    return {
        "internal_retrieved_chunks": internal_chunks,
        "web_retrieved_chunks": web_chunks,
        "web_queries_used": queries,
        "dimension_evidence_map": evidence_map,
        "retrieved_chunks": diversified_chunks,
        "parse_diagnostics": parse_diagnostics,
        "low_confidence": low_confidence,
    }
