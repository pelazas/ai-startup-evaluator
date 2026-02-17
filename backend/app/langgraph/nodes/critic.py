from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.utils.llm import evaluate_with_critic

from ..state import EvaluationState

DIMENSIONS = ("market", "technical", "distribution", "founder_fit", "timing")
LOGGER = logging.getLogger(__name__)

DIMENSION_ALIASES: dict[str, tuple[str, ...]] = {
    "market": ("market", "market_analysis", "marketScore", "market_score"),
    "technical": ("technical", "tech", "technical_feasibility", "technicalScore", "technical_score"),
    "distribution": ("distribution", "gtm", "go_to_market", "distributionScore", "distribution_score"),
    "founder_fit": ("founder_fit", "founderFit", "founder-fit", "founder_fit_score", "founderScore"),
    "timing": ("timing", "timing_assessment", "timingScore", "timing_score"),
}
SCORE_KEYS = ("score", "value", "rating")
RATIONALE_KEYS = ("rationale", "reasoning", "analysis", "justification", "explanation")


class _DimensionSchema(BaseModel):
    score: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)


class _CriticDimensionsSchema(BaseModel):
    market: _DimensionSchema
    technical: _DimensionSchema
    distribution: _DimensionSchema
    founder_fit: _DimensionSchema
    timing: _DimensionSchema


def _coerce_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(0, min(100, value))
    if isinstance(value, float):
        return max(0, min(100, int(round(value))))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            if "." in stripped:
                return max(0, min(100, int(round(float(stripped)))))
            return max(0, min(100, int(stripped)))
        except ValueError:
            return None
    return None


def _coerce_rationale(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _extract_dimension_payload(root: dict[str, Any], dimensions_payload: dict[str, Any], dimension: str) -> Any:
    aliases = DIMENSION_ALIASES[dimension]
    for alias in aliases:
        if alias in dimensions_payload:
            return dimensions_payload[alias]
    for alias in aliases:
        if alias in root:
            return {"score": root[alias]}
    for alias in aliases:
        for suffix in ("_score", "Score"):
            key = f"{alias}{suffix}"
            if key in root:
                rationale = None
                for rationale_suffix in ("_rationale", "_analysis", "_reasoning"):
                    rationale_key = f"{alias}{rationale_suffix}"
                    if rationale_key in root:
                        rationale = root[rationale_key]
                        break
                return {"score": root[key], "rationale": rationale}
    return None


def _normalize_dimension_payload(payload: Any) -> tuple[int | None, dict[str, Any], str | None]:
    if isinstance(payload, (int, float, str)):
        score = _coerce_score(payload)
        if score is None:
            return None, {"rationale": "Unavailable - Invalid score format."}, "invalid_scalar_score"
        return score, {"rationale": "Rationale not provided by critic output."}, None

    if not isinstance(payload, dict):
        return None, {"rationale": "Unavailable - Missing dimension payload."}, "missing_payload"

    score: int | None = None
    for key in SCORE_KEYS:
        if key in payload:
            score = _coerce_score(payload[key])
            if score is not None:
                break
    if score is None:
        for value in payload.values():
            score = _coerce_score(value)
            if score is not None:
                break

    rationale = None
    for key in RATIONALE_KEYS:
        if key in payload:
            rationale = _coerce_rationale(payload[key])
            if rationale:
                break

    if score is None:
        return None, {"rationale": "Unavailable - Unable to parse score for this dimension."}, "score_parse_failed"
    if rationale is None:
        rationale = "Rationale not provided by critic output."
    return score, {"rationale": rationale}, None


def _normalize_score_scale(scores: dict[str, int | None]) -> tuple[dict[str, int | None], bool]:
    available = [value for value in scores.values() if isinstance(value, int)]
    if not available:
        return scores, False
    if max(available) <= 10:
        return ({key: (value * 10 if isinstance(value, int) else None) for key, value in scores.items()}, True)
    return scores, False


def _dimension_context_hint(dimension: str, retrieved_chunks: list[dict[str, Any]]) -> str:
    if not retrieved_chunks:
        return "Evidence coverage was limited."

    top = retrieved_chunks[:5]
    collections = [str(chunk.get("collection") or "unknown") for chunk in top]
    dominant = max(set(collections), key=collections.count)
    source = next((chunk for chunk in top if str(chunk.get("collection")) == dominant), top[0])
    title = str(source.get("title") or source.get("metadata", {}).get("title") or "retrieved source")
    snippet = str(source.get("content") or "").replace("\n", " ").strip()[:180]

    angle = {
        "market": "Market demand and competitive signals",
        "technical": "Technical feasibility and implementation complexity",
        "distribution": "Go-to-market and distribution execution",
        "founder_fit": "Founder background fit for this problem",
        "timing": "Timing and adoption readiness",
    }.get(dimension, "Supporting evidence")
    return f"{angle} inferred from {dominant} evidence (e.g., {title}) with signal: {snippet or 'insufficient excerpt'}."


def _enrich_missing_rationales(
    analyses: dict[str, dict[str, Any]],
    scores: dict[str, int | None],
    retrieved_chunks: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    enriched = dict(analyses)
    for dimension in DIMENSIONS:
        score = scores.get(dimension)
        current = enriched.get(dimension, {})
        rationale = current.get("rationale") if isinstance(current, dict) else None
        needs_fill = not isinstance(rationale, str) or not rationale.strip() or "not provided by critic output" in rationale.lower()
        if needs_fill:
            if isinstance(score, int):
                score_band = "low" if score < 45 else "moderate" if score < 70 else "strong"
                generated = f"Score interpreted as {score_band} confidence for this dimension. {_dimension_context_hint(dimension, retrieved_chunks)}"
            else:
                generated = f"Score unavailable. {_dimension_context_hint(dimension, retrieved_chunks)}"
            enriched[dimension] = {"rationale": generated}
    return enriched


def _validate_strict_dimensions_schema(
    scores: dict[str, int | None],
    analyses: dict[str, dict[str, Any]],
) -> list[str]:
    candidate: dict[str, dict[str, Any]] = {}
    for dimension in DIMENSIONS:
        score = scores.get(dimension)
        rationale = analyses.get(dimension, {}).get("rationale")
        if isinstance(score, int) and isinstance(rationale, str) and rationale.strip():
            candidate[dimension] = {"score": score, "rationale": rationale}

    try:
        _CriticDimensionsSchema.model_validate(candidate)
        return []
    except ValidationError as exc:
        return [f"strict_schema:{err['loc']}:{err['type']}" for err in exc.errors()]


def critic_node(state: EvaluationState) -> EvaluationState:
    critic_result = evaluate_with_critic(
        structured_idea=state.get("structured_idea", {}),
        profile_data=state.get("profile_data", {}),
        retrieved_chunks=state.get("retrieved_chunks", []),
    )

    dimensions_payload = critic_result.get("dimensions", {})
    if not isinstance(dimensions_payload, dict):
        dimensions_payload = {}
    dimension_scores: dict[str, int | None] = {}
    dimension_analyses: dict[str, dict[str, Any]] = {}
    failed_dimensions: list[str] = []
    parse_diagnostics: list[str] = []
    unavailable_count = 0

    for dimension in DIMENSIONS:
        payload = _extract_dimension_payload(critic_result, dimensions_payload, dimension)
        score, analysis, parse_error = _normalize_dimension_payload(payload)
        if score is None:
            unavailable_count += 1
            failed_dimensions.append(dimension)
            if parse_error:
                parse_diagnostics.append(f"{dimension}:{parse_error}")
        dimension_scores[dimension] = score
        dimension_analyses[dimension] = analysis

    dimension_scores, scaled_from_ten = _normalize_score_scale(dimension_scores)
    if scaled_from_ten:
        parse_diagnostics.append("normalized_score_scale:1_to_10_to_100")

    dimension_analyses = _enrich_missing_rationales(
        dimension_analyses,
        dimension_scores,
        state.get("retrieved_chunks", []),
    )

    parse_diagnostics.extend(_validate_strict_dimensions_schema(dimension_scores, dimension_analyses))

    top_risks_raw = critic_result.get("top_risks")
    top_risks: list[str]
    if isinstance(top_risks_raw, list):
        top_risks = [str(item) for item in top_risks_raw[:3]]
    else:
        top_risks = ["Insufficient structured risk output from critic."]

    low_confidence = bool(critic_result.get("low_confidence")) or unavailable_count > 0
    if len(state.get("retrieved_chunks", [])) < 20:
        low_confidence = True
    if parse_diagnostics:
        LOGGER.warning(
            "Critic parse diagnostics for evaluation_id=%s: %s",
            state.get("evaluation_id"),
            ", ".join(parse_diagnostics),
        )

    return {
        "dimension_scores": dimension_scores,
        "dimension_analyses": dimension_analyses,
        "failed_dimensions": failed_dimensions,
        "parse_diagnostics": parse_diagnostics,
        "top_risks": top_risks,
        "low_confidence": low_confidence,
    }
