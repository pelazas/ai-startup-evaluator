from __future__ import annotations

from typing import Any

from app.utils.llm import evaluate_with_critic

from ..state import EvaluationState

DIMENSIONS = ("market", "technical", "distribution", "founder_fit", "timing")


def _normalize_dimension_payload(payload: Any) -> tuple[int | None, dict[str, Any]]:
    if not isinstance(payload, dict):
        return None, {"rationale": "Unavailable - Evaluation Error"}
    score = payload.get("score")
    rationale = payload.get("rationale")
    if not isinstance(score, int):
        return None, {"rationale": "Unavailable - Evaluation Error"}
    bounded = max(0, min(100, score))
    return bounded, {"rationale": rationale if isinstance(rationale, str) and rationale.strip() else "No rationale provided"}


def critic_node(state: EvaluationState) -> EvaluationState:
    critic_result = evaluate_with_critic(
        structured_idea=state.get("structured_idea", {}),
        profile_data=state.get("profile_data", {}),
        retrieved_chunks=state.get("retrieved_chunks", []),
    )

    dimensions_payload = critic_result.get("dimensions", {})
    dimension_scores: dict[str, int | None] = {}
    dimension_analyses: dict[str, dict[str, Any]] = {}
    unavailable_count = 0
    for dimension in DIMENSIONS:
        score, analysis = _normalize_dimension_payload(dimensions_payload.get(dimension))
        if score is None:
            unavailable_count += 1
        dimension_scores[dimension] = score
        dimension_analyses[dimension] = analysis

    top_risks_raw = critic_result.get("top_risks")
    top_risks: list[str]
    if isinstance(top_risks_raw, list):
        top_risks = [str(item) for item in top_risks_raw[:3]]
    else:
        top_risks = ["Insufficient structured risk output from critic."]

    low_confidence = bool(critic_result.get("low_confidence")) or unavailable_count > 0
    if len(state.get("retrieved_chunks", [])) < 20:
        low_confidence = True

    return {
        "dimension_scores": dimension_scores,
        "dimension_analyses": dimension_analyses,
        "top_risks": top_risks,
        "low_confidence": low_confidence,
    }

