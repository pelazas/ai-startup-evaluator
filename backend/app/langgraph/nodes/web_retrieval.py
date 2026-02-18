from __future__ import annotations

from app.services.web_search_service import web_search

from ..state import EvaluationState


def _build_web_queries(state: EvaluationState) -> list[str]:
    idea = state.get("idea_description", "")
    target = state.get("target_customer") or ""
    problem = state.get("problem_statement") or ""
    startup_type = state.get("startup_type") or ""
    market_type = state.get("market_type") or ""

    primary = " ".join([idea, target, problem]).strip()
    market_context = " ".join([startup_type, market_type, "startup market trends 2026"]).strip()
    go_to_market = " ".join([idea[:120], "competitive landscape distribution channels"]).strip()

    candidates = [primary, market_context, go_to_market]
    queries: list[str] = []
    for candidate in candidates:
        normalized = " ".join(candidate.split()).strip()
        if normalized and normalized not in queries:
            queries.append(normalized[:400])
    return queries[:3]


def web_retrieval_node(state: EvaluationState) -> EvaluationState:
    internal_chunks = state.get("retrieved_chunks", [])
    should_run_web = bool(state.get("web_enabled", True))

    if not should_run_web:
        return {
            "internal_retrieved_chunks": internal_chunks,
            "web_retrieved_chunks": [],
            "web_queries_used": [],
            "retrieved_chunks": internal_chunks,
        }

    queries = _build_web_queries(state)
    web_chunks: list[dict] = []
    seen_ids: set[str] = set()
    for query in queries:
        for chunk in web_search(query):
            key = str(chunk.get("id") or "")
            if key and key in seen_ids:
                continue
            if key:
                seen_ids.add(key)
            web_chunks.append(chunk)

    merged = [*internal_chunks, *web_chunks]
    low_confidence = len(merged) < 20
    return {
        "internal_retrieved_chunks": internal_chunks,
        "web_retrieved_chunks": web_chunks,
        "web_queries_used": queries,
        "retrieved_chunks": merged,
        "low_confidence": low_confidence,
    }
