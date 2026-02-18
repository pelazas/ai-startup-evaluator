from __future__ import annotations

import base64
import io
import json
import logging
import re
from textwrap import wrap

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.evaluation import Evaluation
from app.models.profile import ProfileSnapshot
from app.models.user import User
from app.schemas.evaluation import EvaluationCreateRequest, EvaluationExportRequest
from app.services.evaluation_service import (
    create_pending_evaluation,
    persist_evaluation_result,
    run_evaluation_graph_stream,
)
from app.services.profile_service import get_profile_by_user_id

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    REPORTLAB_AVAILABLE = True
except Exception:  # pragma: no cover
    LETTER = (612.0, 792.0)
    ImageReader = None
    canvas = None
    REPORTLAB_AVAILABLE = False

router = APIRouter()
DIMENSIONS = ("market", "technical", "distribution", "founder_fit", "timing")
MAX_HISTORY_LIMIT = 100
LOGGER = logging.getLogger(__name__)


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _failed_dimensions_from_scores(scores: dict[str, int | None]) -> list[str]:
    failed: list[str] = []
    for dimension in DIMENSIONS:
        value = scores.get(dimension)
        if not isinstance(value, int):
            failed.append(dimension)
    return failed


def _extract_meta_from_dimension_analyses(dimension_analyses: dict | None) -> dict:
    if not isinstance(dimension_analyses, dict):
        return {}
    raw_meta = dimension_analyses.get("__meta__")
    return raw_meta if isinstance(raw_meta, dict) else {}


def _evaluation_to_payload(evaluation: Evaluation) -> dict:
    dimension_scores = {
        "market": evaluation.market_score,
        "technical": evaluation.technical_score,
        "distribution": evaluation.distribution_score,
        "founder_fit": evaluation.founder_fit_score,
        "timing": evaluation.timing_score,
    }
    meta = _extract_meta_from_dimension_analyses(evaluation.dimension_analyses)
    return {
        "evaluation_id": evaluation.id,
        "status": evaluation.status,
        "overall_score": evaluation.overall_score,
        "verdict": evaluation.verdict,
        "low_confidence": evaluation.low_confidence,
        "dimension_scores": dimension_scores,
        "dimension_analyses": evaluation.dimension_analyses,
        "top_risks": evaluation.top_risks,
        "evidence_sources": evaluation.evidence_sources,
        "idea_title": meta.get("idea_title"),
        "idea_summary": meta.get("idea_summary"),
        "founder_fit_summary": meta.get("founder_fit_summary"),
        "failed_dimensions": _failed_dimensions_from_scores(dimension_scores),
        "parse_diagnostics": [],
        "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None,
        "error_message": evaluation.error_message,
    }


def _line_writer(pdf: canvas.Canvas):
    y = 760
    page_number = 1
    left = 50
    right = 560

    def write_line(text: str = "", font_name: str = "Helvetica", font_size: int = 11, spacing: int = 16):
        nonlocal y, page_number
        if y < 55:
            pdf.setFont("Helvetica", 9)
            pdf.drawString(left, 35, f"Page {page_number}")
            pdf.showPage()
            page_number += 1
            y = 760
        pdf.setFont(font_name, font_size)
        pdf.drawString(left, y, text[: int((right - left) / (font_size * 0.5))])
        y -= spacing

    def write_paragraph(text: str | None, font_name: str = "Helvetica", font_size: int = 11, spacing: int = 14):
        content = (text or "").strip()
        if not content:
            write_line("-", font_name=font_name, font_size=font_size, spacing=spacing)
            return
        width = max(40, int((right - left) / (font_size * 0.52)))
        for raw_line in content.splitlines():
            wrapped = wrap(raw_line.strip() or " ", width=width)
            for piece in wrapped:
                write_line(piece, font_name=font_name, font_size=font_size, spacing=spacing)

    def reserve_vertical(height: int):
        nonlocal y, page_number
        if y - height < 55:
            pdf.setFont("Helvetica", 9)
            pdf.drawString(left, 35, f"Page {page_number}")
            pdf.showPage()
            page_number += 1
            y = 760
        top = y
        y -= height
        return top

    def get_page_number() -> int:
        return page_number

    return write_line, write_paragraph, reserve_vertical, get_page_number


def _decode_image_data_url(data_url: str | None) -> bytes | None:
    if not isinstance(data_url, str):
        return None
    match = re.match(r"^data:image\/[a-zA-Z0-9.+-]+;base64,(.+)$", data_url.strip(), re.DOTALL)
    if not match:
        return None
    try:
        return base64.b64decode(match.group(1))
    except Exception:
        return None


def _build_evaluation_pdf(
    evaluation: Evaluation,
    profile_snapshot: ProfileSnapshot | None,
    export_request: EvaluationExportRequest | None,
) -> bytes:
    if not REPORTLAB_AVAILABLE or canvas is None:
        raise RuntimeError("PDF export dependency missing: reportlab is not installed.")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    write_line, write_paragraph, reserve_vertical, get_page_number = _line_writer(pdf)

    meta = _extract_meta_from_dimension_analyses(evaluation.dimension_analyses)
    title = (meta.get("idea_title") or "").strip() or "Startup Idea Evaluation Report"

    write_line("Startup Idea Evaluation Report", font_name="Helvetica-Bold", font_size=16, spacing=22)
    write_line(f"Title: {title}", font_name="Helvetica-Bold", font_size=12, spacing=16)
    write_line(f"Evaluation ID: {evaluation.id}")
    write_line(f"Created: {evaluation.created_at.isoformat(sep=' ', timespec='seconds')}")
    write_line()

    write_line("Overall Result", font_name="Helvetica-Bold", font_size=13, spacing=18)
    write_line(f"Status: {evaluation.status}")
    write_line(f"Verdict: {evaluation.verdict or 'UNAVAILABLE'}")
    write_line(f"Overall Score: {evaluation.overall_score if evaluation.overall_score is not None else 'Unavailable'}")
    write_line(f"Low Confidence: {'Yes' if evaluation.low_confidence else 'No'}")
    write_line()

    write_line("Dimension Scores", font_name="Helvetica-Bold", font_size=13, spacing=18)
    dimension_scores = {
        "Market": evaluation.market_score,
        "Technical": evaluation.technical_score,
        "Distribution": evaluation.distribution_score,
        "Founder Fit": evaluation.founder_fit_score,
        "Timing": evaluation.timing_score,
    }
    for label, value in dimension_scores.items():
        score_label = str(value) if isinstance(value, int) else "Unavailable"
        write_line(f"- {label}: {score_label}")
    write_line()

    chart_bytes = _decode_image_data_url(export_request.chart_image_data_url if export_request else None)
    if chart_bytes and ImageReader is not None:
        write_line("Score Radar Chart", font_name="Helvetica-Bold", font_size=13, spacing=18)
        chart_height = 240
        chart_width = 240
        top_y = reserve_vertical(chart_height + 10)
        try:
            pdf.drawImage(
                ImageReader(io.BytesIO(chart_bytes)),
                50,
                top_y - chart_height,
                width=chart_width,
                height=chart_height,
                preserveAspectRatio=True,
                mask="auto",
            )
            write_line()
        except Exception:
            write_line("Unable to render chart image from export payload.")
            write_line()

    write_line("Top Risks", font_name="Helvetica-Bold", font_size=13, spacing=18)
    for risk in (evaluation.top_risks or [])[:3]:
        write_paragraph(f"- {risk}")
    if not evaluation.top_risks:
        write_line("-")
    write_line()

    write_line("Dimension Analysis", font_name="Helvetica-Bold", font_size=13, spacing=18)
    dimension_analyses = evaluation.dimension_analyses if isinstance(evaluation.dimension_analyses, dict) else {}
    for key, label in (
        ("market", "Market"),
        ("technical", "Technical"),
        ("distribution", "Distribution"),
        ("founder_fit", "Founder Fit"),
        ("timing", "Timing"),
    ):
        analysis = dimension_analyses.get(key) if isinstance(dimension_analyses.get(key), dict) else {}
        rationale = analysis.get("rationale") if isinstance(analysis, dict) else None
        write_line(f"{label}:", font_name="Helvetica-Bold", font_size=11, spacing=14)
        write_paragraph(rationale)
    write_line()

    write_line("Idea Input", font_name="Helvetica-Bold", font_size=13, spacing=18)
    write_line("Idea Description:", font_name="Helvetica-Bold", font_size=11, spacing=14)
    write_paragraph(evaluation.idea_description)
    if evaluation.problem_statement:
        write_line("Problem Statement:", font_name="Helvetica-Bold", font_size=11, spacing=14)
        write_paragraph(evaluation.problem_statement)
    if evaluation.target_customer:
        write_line("Target Customer:", font_name="Helvetica-Bold", font_size=11, spacing=14)
        write_paragraph(evaluation.target_customer)
    write_line(f"Startup Type: {evaluation.startup_type or '-'}")
    write_line(f"Market Type: {evaluation.market_type or '-'}")
    write_line()

    write_line("Founder Profile Snapshot", font_name="Helvetica-Bold", font_size=13, spacing=18)
    profile_data = profile_snapshot.profile_data if profile_snapshot else {}
    if not isinstance(profile_data, dict) or not profile_data:
        write_line("-")
    else:
        for key in (
            "full_name",
            "role_title",
            "location_city_country",
            "current_stage",
            "industry_focus",
            "business_model",
            "target_market",
            "team_size",
            "weekly_hours_available",
            "budget_range",
            "distribution_channels",
            "risk_tolerance",
            "preferred_time_to_revenue",
        ):
            value = profile_data.get(key)
            if value is None:
                continue
            if isinstance(value, list):
                text = ", ".join(str(item) for item in value)
            else:
                text = str(value)
            write_paragraph(f"{key.replace('_', ' ').title()}: {text}")

    if isinstance(evaluation.evidence_sources, list) and evaluation.evidence_sources:
        write_line()
        write_line("Evidence Sources", font_name="Helvetica-Bold", font_size=13, spacing=18)
        for source in evaluation.evidence_sources[:20]:
            if not isinstance(source, dict):
                continue
            source_title = source.get("title") or source.get("doc_name") or "Untitled source"
            source_url = source.get("source_url") or ""
            detail = f"- {source_title}"
            if source_url:
                detail += f" ({source_url})"
            write_paragraph(detail)

    pdf.setFont("Helvetica", 9)
    pdf.drawString(50, 35, f"Page {get_page_number()}")
    pdf.save()
    return buffer.getvalue()


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
            "web_enabled": request.web_enabled,
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
            LOGGER.exception("Evaluation graph failed for evaluation_id=%s", evaluation.id)
            caught_error = str(exc)

        if caught_error:
            persisted = persist_evaluation_result(db=db, evaluation=evaluation, state=final_state, error_message=caught_error)
            dimension_scores = {
                "market": persisted.market_score,
                "technical": persisted.technical_score,
                "distribution": persisted.distribution_score,
                "founder_fit": persisted.founder_fit_score,
                "timing": persisted.timing_score,
            }
            meta = _extract_meta_from_dimension_analyses(persisted.dimension_analyses)
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
                        "dimension_scores": dimension_scores,
                        "dimension_analyses": persisted.dimension_analyses,
                        "top_risks": persisted.top_risks,
                        "evidence_sources": persisted.evidence_sources,
                        "idea_title": final_state.get("idea_title") or meta.get("idea_title"),
                        "idea_summary": final_state.get("idea_summary") or meta.get("idea_summary"),
                        "founder_fit_summary": final_state.get("founder_fit_summary") or meta.get("founder_fit_summary"),
                        "web_enabled": request.web_enabled,
                        "web_queries_used": final_state.get("web_queries_used", []),
                        "evidence_mix": final_state.get("evidence_mix"),
                        "failed_dimensions": _failed_dimensions_from_scores(dimension_scores),
                        "parse_diagnostics": final_state.get("parse_diagnostics", []),
                        "error_message": persisted.error_message,
                    },
                }
            )
            return

        persisted = persist_evaluation_result(db=db, evaluation=evaluation, state=final_state, error_message=None)
        dimension_scores = {
            "market": persisted.market_score,
            "technical": persisted.technical_score,
            "distribution": persisted.distribution_score,
            "founder_fit": persisted.founder_fit_score,
            "timing": persisted.timing_score,
        }
        meta = _extract_meta_from_dimension_analyses(persisted.dimension_analyses)
        yield _sse(
            {
                "type": "result",
                "data": {
                    "evaluation_id": persisted.id,
                    "status": persisted.status,
                    "overall_score": persisted.overall_score,
                    "verdict": persisted.verdict,
                    "low_confidence": persisted.low_confidence,
                    "dimension_scores": dimension_scores,
                    "dimension_analyses": persisted.dimension_analyses,
                    "top_risks": persisted.top_risks,
                    "evidence_sources": persisted.evidence_sources,
                    "idea_title": final_state.get("idea_title") or meta.get("idea_title"),
                    "idea_summary": final_state.get("idea_summary") or meta.get("idea_summary"),
                    "founder_fit_summary": final_state.get("founder_fit_summary") or meta.get("founder_fit_summary"),
                    "web_enabled": request.web_enabled,
                    "web_queries_used": final_state.get("web_queries_used", []),
                    "evidence_mix": final_state.get("evidence_mix"),
                    "failed_dimensions": _failed_dimensions_from_scores(dimension_scores),
                    "parse_diagnostics": final_state.get("parse_diagnostics", []),
                    "error_message": persisted.error_message,
                },
            }
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("")
def list_evaluations(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_limit = min(max(limit, 1), MAX_HISTORY_LIMIT)
    rows = (
        db.query(Evaluation)
        .filter(Evaluation.user_id == current_user.id)
        .order_by(desc(Evaluation.created_at))
        .limit(safe_limit)
        .all()
    )
    return [_evaluation_to_payload(row) for row in rows]


@router.get("/{evaluation_id}")
def get_evaluation(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    evaluation = (
        db.query(Evaluation)
        .filter(Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id)
        .order_by(desc(Evaluation.created_at))
        .first()
    )
    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")
    return _evaluation_to_payload(evaluation)


@router.post("/{evaluation_id}/export")
def export_evaluation_pdf(
    evaluation_id: str,
    export_request: EvaluationExportRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF export unavailable on this environment (missing reportlab dependency).",
        )

    evaluation = (
        db.query(Evaluation)
        .filter(Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id)
        .order_by(desc(Evaluation.created_at))
        .first()
    )
    if evaluation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found.")

    profile_snapshot = db.query(ProfileSnapshot).filter(ProfileSnapshot.id == evaluation.profile_snapshot_id).first()

    pdf_bytes = _build_evaluation_pdf(
        evaluation=evaluation,
        profile_snapshot=profile_snapshot,
        export_request=export_request,
    )
    filename = f"evaluation-{evaluation.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
