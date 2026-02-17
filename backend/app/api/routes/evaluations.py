from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.evaluation import EvaluationCreateRequest
from app.services.evaluation_service import (
    create_pending_evaluation,
    persist_evaluation_result,
    run_evaluation_graph_stream,
)
from app.services.profile_service import get_profile_by_user_id

router = APIRouter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("")
def create_evaluation(
    request: EvaluationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    def event_generator():
        profile = get_profile_by_user_id(db, current_user.id)
        if profile is None:
            yield _sse({"type": "error", "message": "Profile is required before evaluation."})
            return

        evaluation = create_pending_evaluation(db=db, user_id=current_user.id, payload=request)

        state = {
            "evaluation_id": evaluation.id,
            "idea_description": request.idea_description,
            "target_customer": request.target_customer,
            "problem_statement": request.problem_statement,
            "startup_type": request.startup_type,
            "market_type": request.market_type,
            "profile_data": {
                key: value
                for key, value in profile.__dict__.items()
                if not key.startswith("_")
                and key
                not in {
                    "id",
                    "user_id",
                    "created_at",
                    "updated_at",
                }
            },
        }

        final_state = dict(state)
        caught_error: str | None = None
        try:
            for event in run_evaluation_graph_stream(db=db, initial_state=state):
                if event.get("type") == "state":
                    final_state.update(event.get("data", {}))
                    continue
                yield _sse(event)
        except Exception as exc:
            caught_error = str(exc)

        if caught_error:
            persisted = persist_evaluation_result(db=db, evaluation=evaluation, state=final_state, error_message=caught_error)
            yield _sse({"type": "error", "message": caught_error})
            yield _sse(
                {
                    "type": "result",
                    "data": {
                        "evaluation_id": persisted.id,
                        "status": persisted.status,
                        "overall_score": persisted.overall_score,
                        "verdict": persisted.verdict,
                        "low_confidence": persisted.low_confidence,
                    },
                }
            )
            return

        persisted = persist_evaluation_result(db=db, evaluation=evaluation, state=final_state, error_message=None)
        yield _sse(
            {
                "type": "result",
                "data": {
                    "evaluation_id": persisted.id,
                    "status": persisted.status,
                    "overall_score": persisted.overall_score,
                    "verdict": persisted.verdict,
                    "low_confidence": persisted.low_confidence,
                    "dimension_scores": {
                        "market": persisted.market_score,
                        "technical": persisted.technical_score,
                        "distribution": persisted.distribution_score,
                        "founder_fit": persisted.founder_fit_score,
                        "timing": persisted.timing_score,
                    },
                    "dimension_analyses": persisted.dimension_analyses,
                    "top_risks": persisted.top_risks,
                    "evidence_sources": persisted.evidence_sources,
                },
            }
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

