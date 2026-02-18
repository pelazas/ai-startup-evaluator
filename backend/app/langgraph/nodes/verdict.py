from __future__ import annotations

from typing import Any

from app.utils.llm import generate_explanatory_summaries

from ..state import EvaluationState


COLLECTION_DIMENSION_HINTS: dict[str, list[str]] = {
    "founder_principles": ["founder_fit", "distribution"],
    "ai_market_data": ["market", "timing"],
    "startup_examples": ["distribution", "market"],
    "technical_constraints": ["technical", "timing"],
    "personal_profile": ["founder_fit"],
    "web": ["market", "technical", "distribution", "founder_fit", "timing"],
}
DIMENSION_LABELS: dict[str, str] = {
    "market": "market opportunity",
    "technical": "technical feasibility",
    "distribution": "distribution execution",
    "founder_fit": "founder-idea fit",
    "timing": "timing readiness",
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


def _chunk_match_key(chunk: dict[str, Any], collection: str, title: str) -> str:
    chunk_id = _clean_text(chunk.get("id"))
    if chunk_id:
        return f"id::{chunk_id}"
    return f"title::{collection}::{title.lower()}"


def _build_evidence_sources(
    chunks: list[dict[str, Any]],
    dimension_evidence_map: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    seen_title_collection: set[tuple[str, str]] = set()
    source_dimensions: dict[str, set[str]] = {}

    if isinstance(dimension_evidence_map, dict):
        for dimension, scoped_chunks in dimension_evidence_map.items():
            if not isinstance(scoped_chunks, list):
                continue
            for scoped_chunk in scoped_chunks:
                if not isinstance(scoped_chunk, dict):
                    continue
                scoped_metadata = scoped_chunk.get("metadata") if isinstance(scoped_chunk.get("metadata"), dict) else {}
                scoped_collection = _clean_text(scoped_chunk.get("collection")) or "unknown"
                scoped_title = (
                    _clean_text(scoped_chunk.get("title"))
                    or _clean_text(scoped_metadata.get("title"))
                    or _clean_text(scoped_metadata.get("document_title"))
                    or _clean_text(scoped_metadata.get("doc_name"))
                    or "Untitled source"
                )
                key = _chunk_match_key(scoped_chunk, scoped_collection, scoped_title)
                source_dimensions.setdefault(key, set()).add(dimension)

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
        match_key = _chunk_match_key(chunk, collection, title)
        mapped_hints = sorted(source_dimensions.get(match_key, set()))
        dimension_hints = mapped_hints or COLLECTION_DIMENSION_HINTS.get(collection, [])

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


def _score_band(score: int | None) -> str:
    if not isinstance(score, int):
        return "unknown"
    if score >= 75:
        return "strong"
    if score >= 55:
        return "moderate"
    return "weak"


def _compact_rationale(value: Any, fallback: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return fallback
    lowered = cleaned.lower()
    if "rationale not provided by critic output" in lowered:
        return fallback
    if len(cleaned) > 260:
        return f"{cleaned[:257].rstrip()}..."
    return cleaned


def _build_idea_summary(state: EvaluationState, overall: int | None, verdict: str | None) -> str:
    scores = state.get("dimension_scores", {})
    analyses = state.get("dimension_analyses", {})
    top_risks = state.get("top_risks") or []
    if not isinstance(top_risks, list):
        top_risks = []
    idea_title = _clean_text(state.get("idea_title")) or "this startup idea"
    evidence_mix = state.get("evidence_mix") if isinstance(state.get("evidence_mix"), dict) else {}

    best_dim = None
    worst_dim = None
    numeric_scores = {key: value for key, value in scores.items() if isinstance(value, int)}
    if numeric_scores:
        best_dim = max(numeric_scores, key=numeric_scores.get)
        worst_dim = min(numeric_scores, key=numeric_scores.get)

    best_rationale = _compact_rationale(
        (analyses.get(best_dim or "", {}) if isinstance(analyses.get(best_dim or ""), dict) else {}).get("rationale"),
        "Evidence suggests a meaningful upside if execution is disciplined.",
    )
    worst_rationale = _compact_rationale(
        (analyses.get(worst_dim or "", {}) if isinstance(analyses.get(worst_dim or ""), dict) else {}).get("rationale"),
        "The weakest dimension still needs sharper validation and execution proof.",
    )

    if overall is None:
        return f"{idea_title} could not be fully scored due to missing outputs. The current evidence is insufficient for a reliable final decision."

    best_label = DIMENSION_LABELS.get(best_dim or "", "strength")
    worst_label = DIMENSION_LABELS.get(worst_dim or "", "risk")
    risk_line = f" Key risk to resolve next: {top_risks[0]}." if top_risks else ""
    evidence_line = ""
    total_sources = evidence_mix.get("total_sources")
    if isinstance(total_sources, int):
        evidence_line = f" Confidence is based on {total_sources} evidence source{'s' if total_sources != 1 else ''}."
    return (
        f"{idea_title} is currently {verdict or 'UNAVAILABLE'} at {overall}/100. "
        f"This score is pulled up by {best_label} ({_score_band(numeric_scores.get(best_dim) if best_dim else None)}), where the evidence suggests {best_rationale.lower()} "
        f"It is pulled down by {worst_label} ({_score_band(numeric_scores.get(worst_dim) if worst_dim else None)}), because {worst_rationale.lower()}{risk_line}{evidence_line}"
    )


def _build_founder_fit_summary(state: EvaluationState) -> str:
    scores = state.get("dimension_scores", {})
    profile = state.get("profile_data", {})
    score = scores.get("founder_fit") if isinstance(scores, dict) else None
    if not isinstance(profile, dict):
        profile = {}

    strengths: list[str] = []
    risks: list[str] = []

    technical_levels = [
        profile.get("cloud_deployment_level"),
        profile.get("ai_coding_agents_level"),
        profile.get("backend_engineering_level"),
        profile.get("product_ux_level"),
        profile.get("data_ml_engineering_level"),
    ]
    strong_technical = sum(
        1
        for value in technical_levels
        if isinstance(value, str) and value.strip().lower() in {"advanced", "expert"}
    )
    weak_technical = sum(
        1
        for value in technical_levels
        if isinstance(value, str) and value.strip().lower() in {"none", "basic"}
    )
    if strong_technical >= 2:
        strengths.append("the technical execution baseline is strong enough to ship and iterate quickly")
    elif weak_technical >= 2:
        risks.append("the current technical stack depth may slow execution velocity and product reliability")

    domain_level = profile.get("domain_expertise_level")
    if isinstance(domain_level, int):
        if domain_level >= 4:
            strengths.append("domain familiarity appears high, which improves product judgment and prioritization")
        elif domain_level <= 2:
            risks.append("domain familiarity appears limited, increasing discovery and positioning risk")

    channels = profile.get("distribution_channels")
    sales_experience = str(profile.get("sales_experience") or "").strip().lower()
    audience_access = str(profile.get("audience_access") or "").strip().lower()
    has_distribution = isinstance(channels, list) and len(channels) >= 2
    if has_distribution and sales_experience in {"some", "strong"}:
        strengths.append("there are usable go-to-market paths, reducing early distribution uncertainty")
    else:
        risks.append("go-to-market execution is a primary risk without stronger channel access and sales motion")
    if audience_access in {"none", "", "<1k"}:
        risks.append("limited owned audience means customer acquisition may depend on slower outbound or paid motion")

    hours = profile.get("weekly_hours_available")
    if isinstance(hours, int):
        if hours >= 30:
            strengths.append("available weekly founder bandwidth is high enough for consistent execution")
        elif hours <= 15:
            risks.append("limited weekly availability may delay validation loops and reduce learning speed")

    team_size = str(profile.get("team_size") or "").strip().lower()
    hiring_ability = str(profile.get("hiring_ability") or "").strip().lower()
    if team_size in {"solo"} and hiring_ability in {"none"}:
        risks.append("a solo setup with limited hiring capacity can become a bottleneck after initial build")
    elif hiring_ability in {"1-2", "3+"}:
        strengths.append("ability to add talent reduces execution bottlenecks as scope expands")

    constraints = []
    if bool(profile.get("regulatory_constraints")):
        constraints.append("regulatory")
    if bool(profile.get("ip_constraints")):
        constraints.append("IP")
    if bool(profile.get("geo_legal_constraints")):
        constraints.append("geo-legal")
    if constraints:
        risks.append(f"{', '.join(constraints)} constraints may slow launch and increase compliance overhead")

    strengths = [item for idx, item in enumerate(strengths) if item not in strengths[:idx]]
    risks = [item for idx, item in enumerate(risks) if item not in risks[:idx]]

    strengths_text = "; ".join(strengths[:2]) if strengths else "founder strengths are present but not yet fully evidenced"
    risks_text = "; ".join(risks[:2]) if risks else "major execution blockers are not obvious, but distribution proof is still required"

    if isinstance(score, int):
        return (
            f"Founder-Idea fit is {score}/100 ({_score_band(score)}). "
            f"This looks credible because {strengths_text}. "
            f"It is still constrained because {risks_text}. "
            "The idea can work if execution stays narrowly focused on a specific ICP and early repeatable distribution signal."
        )
    return (
        "Founder-Idea fit is currently unavailable from this run. "
        f"Based on profile context, the opportunity looks stronger when {strengths_text}, "
        f"but risk remains high when {risks_text}."
    )


def _summary_needs_rewrite(text: str) -> bool:
    lowered = text.lower()
    bad_patterns = (
        "score interpreted as",
        "inferred from",
        "evidence (e.g.",
        "source:",
        "rationale not provided",
    )
    return any(pattern in lowered for pattern in bad_patterns)


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

    dimension_evidence_map = (
        state.get("dimension_evidence_map")
        if isinstance(state.get("dimension_evidence_map"), dict)
        else {}
    )
    evidence_sources = _build_evidence_sources(
        state.get("retrieved_chunks", []),
        dimension_evidence_map=dimension_evidence_map,
    )
    web_count = len([source for source in evidence_sources if source.get("collection") == "web"])
    internal_count = len(evidence_sources) - web_count
    evidence_mix = {
        "internal_sources": internal_count,
        "web_sources": web_count,
        "total_sources": len(evidence_sources),
    }
    state_with_sources = dict(state)
    state_with_sources["evidence_sources"] = evidence_sources
    state_with_sources["evidence_mix"] = evidence_mix
    idea_summary = _build_idea_summary(state_with_sources, overall, verdict)
    founder_fit_summary = _build_founder_fit_summary(state_with_sources)

    generated = generate_explanatory_summaries(
        idea_title=_clean_text(state.get("idea_title")) or "Startup idea",
        idea_description=_clean_text(state.get("idea_description")) or "",
        dimension_scores=scores if isinstance(scores, dict) else {},
        dimension_analyses=state.get("dimension_analyses", {}) if isinstance(state.get("dimension_analyses"), dict) else {},
        top_risks=state.get("top_risks", []) if isinstance(state.get("top_risks"), list) else [],
        evidence_mix=evidence_mix,
        profile_data=state.get("profile_data", {}) if isinstance(state.get("profile_data"), dict) else {},
        verdict=verdict,
        overall_score=overall,
    )
    if isinstance(generated, dict):
        candidate_idea = generated.get("idea_summary", idea_summary)
        candidate_founder = generated.get("founder_fit_summary", founder_fit_summary)
        if isinstance(candidate_idea, str) and candidate_idea.strip():
            idea_summary = candidate_idea
        if isinstance(candidate_founder, str) and candidate_founder.strip() and not _summary_needs_rewrite(candidate_founder):
            founder_fit_summary = candidate_founder

    return {
        "overall_score": overall,
        "verdict": verdict,
        "evidence_sources": evidence_sources,
        "evidence_mix": evidence_mix,
        "idea_summary": idea_summary,
        "founder_fit_summary": founder_fit_summary,
    }
