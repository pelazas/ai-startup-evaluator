from __future__ import annotations

from ..state import EvaluationState


def verdict_node(state: EvaluationState) -> EvaluationState:
    scores = state.get("dimension_scores", {})
    available = [value for value in scores.values() if isinstance(value, int)]
    overall = int(round(sum(available) / len(available))) if available else 0

    if overall >= 70:
        verdict = "GO"
    elif overall >= 55:
        verdict = "CONDITIONAL"
    else:
        verdict = "NO-GO"

    evidence_sources = []
    for chunk in state.get("retrieved_chunks", []):
        evidence_sources.append(
            {
                "doc_name": chunk.get("title") or chunk.get("id"),
                "collection": chunk.get("collection"),
                "source": chunk.get("source"),
                "chunk_id": chunk.get("id"),
            }
        )

    return {
        "overall_score": overall,
        "verdict": verdict,
        "evidence_sources": evidence_sources,
    }

