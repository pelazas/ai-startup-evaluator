from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.langgraph.graph import build_evaluation_graph
from app.langgraph.state import EvaluationState
from app.models.evaluation import Evaluation
from app.schemas.evaluation import EvaluationCreateRequest
from app.services.profile_service import get_or_create_profile_snapshot

DIMENSIONS = ("market", "technical", "distribution", "founder_fit", "timing")
NODE_NAME_ALIASES = {"verdict_step": "verdict"}
LOGGER = logging.getLogger(__name__)


def create_pending_evaluation(db: Session, user_id: str, payload: EvaluationCreateRequest) -> Evaluation:
    snapshot = get_or_create_profile_snapshot(db, user_id=user_id)
    evaluation = Evaluation(
        user_id=user_id,
        profile_snapshot_id=snapshot.id,
        idea_description=payload.idea_description,
        target_customer=payload.target_customer,
        problem_statement=payload.problem_statement,
        startup_type=payload.startup_type,
        market_type=payload.market_type,
        idea_tags=[],
        idea_folder=None,
        status="pending",
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def _normalize_dimension_outcomes(
    scores: dict[str, int | None],
    analyses: dict[str, dict[str, Any]],
    failed_dimensions_hint: list[str] | None = None,
) -> tuple[dict[str, int | None], dict[str, dict[str, Any]], list[str], int]:
    final_scores = dict(scores)
    final_analyses = dict(analyses)
    failed_dimensions: list[str] = []

    for dimension in DIMENSIONS:
        score = final_scores.get(dimension)
        if not isinstance(score, int):
            final_scores[dimension] = None
            existing_analysis = final_analyses.get(dimension, {})
            rationale = existing_analysis.get("rationale") if isinstance(existing_analysis, dict) else None
            final_analyses[dimension] = {
                "rationale": rationale if isinstance(rationale, str) and rationale.strip() else "Unavailable - Evaluation Error"
            }
            failed_dimensions.append(dimension)

    hinted_failed = {value for value in (failed_dimensions_hint or []) if value in DIMENSIONS}
    for dimension in hinted_failed:
        if dimension not in failed_dimensions:
            failed_dimensions.append(dimension)

    success_count = len(DIMENSIONS) - len(failed_dimensions)
    return final_scores, final_analyses, failed_dimensions, success_count


def persist_evaluation_result(
    db: Session,
    evaluation: Evaluation,
    state: EvaluationState,
    error_message: str | None = None,
) -> Evaluation:
    dimension_scores = state.get("dimension_scores", {})
    dimension_analyses = state.get("dimension_analyses", {})
    dimension_scores, dimension_analyses, _, success_count = _normalize_dimension_outcomes(
        dimension_scores,
        dimension_analyses,
        state.get("failed_dimensions"),
    )

    evaluation.market_score = dimension_scores["market"]
    evaluation.technical_score = dimension_scores["technical"]
    evaluation.distribution_score = dimension_scores["distribution"]
    evaluation.founder_fit_score = dimension_scores["founder_fit"]
    evaluation.timing_score = dimension_scores["timing"]
    meta = {
        "idea_title": state.get("idea_title"),
        "idea_summary": state.get("idea_summary"),
        "founder_fit_summary": state.get("founder_fit_summary"),
    }
    stored_dimension_analyses = dict(dimension_analyses)
    stored_dimension_analyses["__meta__"] = meta

    evaluation.dimension_analyses = stored_dimension_analyses
    evaluation.top_risks = state.get("top_risks")
    evaluation.evidence_sources = state.get("evidence_sources")
    tags = state.get("idea_tags")
    evaluation.idea_tags = [str(item).strip().lower() for item in tags] if isinstance(tags, list) else []
    folder = state.get("idea_folder")
    evaluation.idea_folder = str(folder).strip() if isinstance(folder, str) and str(folder).strip() else None
    evaluation.low_confidence = bool(state.get("low_confidence", False))
    evaluation.error_message = error_message

    if success_count > 0:
        available_scores = [value for value in dimension_scores.values() if isinstance(value, int)]
        computed_overall = int(round(sum(available_scores) / len(available_scores))) if available_scores else None
        stored_overall = state.get("overall_score")
        evaluation.overall_score = stored_overall if isinstance(stored_overall, int) else computed_overall
        stored_verdict = state.get("verdict")
        evaluation.verdict = stored_verdict if isinstance(stored_verdict, str) else None
    else:
        evaluation.overall_score = None
        evaluation.verdict = None

    if success_count == 0:
        evaluation.status = "failed"
    elif success_count < len(DIMENSIONS):
        evaluation.status = "partial"
    else:
        evaluation.status = "completed"

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def run_evaluation_graph_stream(db: Session, initial_state: EvaluationState):
    graph = build_evaluation_graph(db)
    merged_state: EvaluationState = dict(initial_state)

    for update in graph.stream(initial_state):
        if not isinstance(update, dict):
            continue
        for node_name, node_payload in update.items():
            if isinstance(node_payload, dict):
                merged_state.update(node_payload)
            public_node = NODE_NAME_ALIASES.get(node_name, node_name)
            yield {
                "type": "progress",
                "node": public_node,
                "status": "completed",
            }

    yield {"type": "state", "data": merged_state}
