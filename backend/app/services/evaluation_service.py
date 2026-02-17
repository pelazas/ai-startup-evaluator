from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.langgraph.graph import build_evaluation_graph
from app.langgraph.state import EvaluationState
from app.models.evaluation import Evaluation
from app.schemas.evaluation import EvaluationCreateRequest
from app.services.profile_service import get_or_create_profile_snapshot

DIMENSIONS = ("market", "technical", "distribution", "founder_fit", "timing")


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
        status="pending",
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def _mark_unavailable_dimensions(scores: dict[str, int | None], analyses: dict[str, dict[str, Any]]) -> tuple[dict[str, int | None], dict[str, dict[str, Any]], bool]:
    partial = False
    final_scores = dict(scores)
    final_analyses = dict(analyses)
    for dimension in DIMENSIONS:
        if dimension not in final_scores or final_scores[dimension] is None:
            partial = True
            final_scores[dimension] = None
            final_analyses[dimension] = {"rationale": "Unavailable - Evaluation Error"}
    return final_scores, final_analyses, partial


def persist_evaluation_result(
    db: Session,
    evaluation: Evaluation,
    state: EvaluationState,
    error_message: str | None = None,
) -> Evaluation:
    dimension_scores = state.get("dimension_scores", {})
    dimension_analyses = state.get("dimension_analyses", {})
    dimension_scores, dimension_analyses, partial = _mark_unavailable_dimensions(dimension_scores, dimension_analyses)

    evaluation.market_score = dimension_scores["market"]
    evaluation.technical_score = dimension_scores["technical"]
    evaluation.distribution_score = dimension_scores["distribution"]
    evaluation.founder_fit_score = dimension_scores["founder_fit"]
    evaluation.timing_score = dimension_scores["timing"]
    evaluation.dimension_analyses = dimension_analyses
    evaluation.top_risks = state.get("top_risks")
    evaluation.evidence_sources = state.get("evidence_sources")
    evaluation.low_confidence = bool(state.get("low_confidence", False))
    evaluation.overall_score = state.get("overall_score")
    evaluation.verdict = state.get("verdict")
    evaluation.error_message = error_message

    has_any_score = any(isinstance(value, int) for value in dimension_scores.values())
    if error_message and not has_any_score:
        evaluation.status = "failed"
    elif partial:
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
            yield {
                "type": "progress",
                "node": node_name,
                "status": "completed",
            }

    yield {"type": "state", "data": merged_state}

