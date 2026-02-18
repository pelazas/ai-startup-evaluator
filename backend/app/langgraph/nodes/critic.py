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

LEVEL_TO_SCORE = {
    "none": 20,
    "basic": 40,
    "intermediate": 60,
    "advanced": 80,
    "expert": 92,
}


def _clamp_score(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def _profile_level_score(value: Any, default: int = 55) -> int:
    if isinstance(value, str):
        mapped = LEVEL_TO_SCORE.get(value.strip().lower())
        if mapped is not None:
            return mapped
    return default


def _profile_founder_fit_heuristic(profile_data: dict[str, Any]) -> tuple[int, str]:
    # Technical execution capability.
    technical_fields = (
        "cloud_deployment_level",
        "ai_coding_agents_level",
        "backend_engineering_level",
        "product_ux_level",
        "data_ml_engineering_level",
    )
    technical_values = [_profile_level_score(profile_data.get(field)) for field in technical_fields]
    technical_score = _clamp_score(sum(technical_values) / len(technical_values)) if technical_values else 55

    # Domain familiarity.
    domain_level = profile_data.get("domain_expertise_level")
    if isinstance(domain_level, int):
        domain_score = _clamp_score(20 + (domain_level * 15))
    else:
        domain_score = 55

    # Distribution readiness from channels, sales experience, audience access.
    channels = profile_data.get("distribution_channels")
    channels_count = len(channels) if isinstance(channels, list) else 0
    channel_score = 35 + min(35, channels_count * 7)
    sales_exp = str(profile_data.get("sales_experience") or "").strip().lower()
    sales_score = {"none": 30, "some": 60, "strong": 85}.get(sales_exp, 50)
    audience = str(profile_data.get("audience_access") or "").strip().lower()
    audience_score = {"none": 25, "<1k": 40, "1k-10k": 65, "10k+": 85}.get(audience, 50)
    distribution_score = _clamp_score((channel_score + sales_score + audience_score) / 3)

    # Execution capacity.
    weekly_hours = profile_data.get("weekly_hours_available")
    if isinstance(weekly_hours, int):
        hours_score = _clamp_score(20 + min(65, weekly_hours * 1.2))
    else:
        hours_score = 55
    hiring = str(profile_data.get("hiring_ability") or "").strip().lower()
    hiring_score = {"none": 35, "1-2": 65, "3+": 80}.get(hiring, 50)
    team_size = str(profile_data.get("team_size") or "").strip().lower()
    team_score = {"solo": 45, "2-3": 65, "4-10": 78, "10+": 82}.get(team_size, 55)
    capacity_score = _clamp_score((hours_score + hiring_score + team_score) / 3)

    # Hard constraint penalty.
    penalty = 0
    if bool(profile_data.get("regulatory_constraints")):
        penalty += 5
    if bool(profile_data.get("ip_constraints")):
        penalty += 5
    if bool(profile_data.get("geo_legal_constraints")):
        penalty += 5

    heuristic = _clamp_score(
        (technical_score * 0.35)
        + (domain_score * 0.20)
        + (distribution_score * 0.25)
        + (capacity_score * 0.20)
        - penalty
    )
    rationale = (
        f"Founder fit calibrated from profile: technical readiness {technical_score}/100, "
        f"domain familiarity {domain_score}/100, distribution readiness {distribution_score}/100, "
        f"execution capacity {capacity_score}/100"
        + (f", with constraints penalty {penalty}." if penalty else ".")
    )
    return heuristic, rationale


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


def _dimension_context_hint(
    dimension: str,
    retrieved_chunks: list[dict[str, Any]],
    dimension_evidence_map: dict[str, list[dict[str, Any]]] | None = None,
) -> str:
    scoped_chunks = []
    if isinstance(dimension_evidence_map, dict):
        scoped = dimension_evidence_map.get(dimension)
        if isinstance(scoped, list):
            scoped_chunks = scoped
    candidates = scoped_chunks or retrieved_chunks
    if not candidates:
        return "Evidence coverage was limited."

    top = candidates[:5]
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
    dimension_evidence_map: dict[str, list[dict[str, Any]]] | None = None,
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
                generated = (
                    f"Score interpreted as {score_band} confidence for this dimension. "
                    f"{_dimension_context_hint(dimension, retrieved_chunks, dimension_evidence_map)}"
                )
            else:
                generated = f"Score unavailable. {_dimension_context_hint(dimension, retrieved_chunks, dimension_evidence_map)}"
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
    dimension_evidence_map = (
        state.get("dimension_evidence_map")
        if isinstance(state.get("dimension_evidence_map"), dict)
        else {}
    )
    critic_result = evaluate_with_critic(
        structured_idea=state.get("structured_idea", {}),
        profile_data=state.get("profile_data", {}),
        retrieved_chunks=state.get("retrieved_chunks", []),
        dimension_evidence_map=dimension_evidence_map,
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
        dimension_evidence_map,
    )

    parse_diagnostics.extend(_validate_strict_dimensions_schema(dimension_scores, dimension_analyses))

    profile_data = state.get("profile_data", {})
    if not isinstance(profile_data, dict):
        profile_data = {}
    heuristic_founder_fit, heuristic_rationale = _profile_founder_fit_heuristic(profile_data)
    llm_founder_fit = dimension_scores.get("founder_fit")
    if isinstance(llm_founder_fit, int):
        blended = _clamp_score((llm_founder_fit * 0.6) + (heuristic_founder_fit * 0.4))
        dimension_scores["founder_fit"] = blended
        existing = dimension_analyses.get("founder_fit", {})
        existing_rationale = existing.get("rationale") if isinstance(existing, dict) else None
        dimension_analyses["founder_fit"] = {
            "rationale": (
                f"{existing_rationale if isinstance(existing_rationale, str) else 'Founder fit assessed from critic output.'} "
                f"{heuristic_rationale}"
            ).strip()
        }
        parse_diagnostics.append(f"founder_fit_blended:llm={llm_founder_fit},profile={heuristic_founder_fit}")
    else:
        dimension_scores["founder_fit"] = heuristic_founder_fit
        dimension_analyses["founder_fit"] = {"rationale": heuristic_rationale}
        if "founder_fit" in failed_dimensions:
            failed_dimensions = [dim for dim in failed_dimensions if dim != "founder_fit"]
        parse_diagnostics.append("founder_fit_filled_from_profile")

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
