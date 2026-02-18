from __future__ import annotations

import base64
import io
import json
import logging
import re
from html import escape as html_escape

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
from app.services.keyword_trends_service import build_google_keyword_trends
from app.services.profile_service import get_profile_by_user_id
from app.utils.llm import parse_filter_tags

try:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    REPORTLAB_AVAILABLE = True
except Exception:  # pragma: no cover
    LETTER = (612.0, 792.0)
    ParagraphStyle = None
    getSampleStyleSheet = None
    inch = 72.0
    colors = None
    Image = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None
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
        "idea_description": evaluation.idea_description,
        "target_customer": evaluation.target_customer,
        "problem_statement": evaluation.problem_statement,
        "startup_type": evaluation.startup_type,
        "market_type": evaluation.market_type,
        "status": evaluation.status,
        "overall_score": evaluation.overall_score,
        "verdict": evaluation.verdict,
        "low_confidence": evaluation.low_confidence,
        "dimension_scores": dimension_scores,
        "dimension_analyses": evaluation.dimension_analyses,
        "top_risks": evaluation.top_risks,
        "evidence_sources": evaluation.evidence_sources,
        "idea_title": meta.get("idea_title"),
        "idea_categorization": meta.get("idea_categorization"),
        "idea_summary": meta.get("idea_summary"),
        "founder_fit_summary": meta.get("founder_fit_summary"),
        "idea_tags": evaluation.idea_tags or [],
        "idea_folder": evaluation.idea_folder,
        "failed_dimensions": _failed_dimensions_from_scores(dimension_scores),
        "parse_diagnostics": [],
        "created_at": evaluation.created_at.isoformat() if evaluation.created_at else None,
        "error_message": evaluation.error_message,
    }


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


def _safe_text(value: str | None, fallback: str = "-") -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip()
    return cleaned if cleaned else fallback


def _safe_paragraph_text(value: str | None, fallback: str = "-") -> str:
    return html_escape(_safe_text(value, fallback))


def _resolve_brand_color(export_request: EvaluationExportRequest | None):
    raw = (export_request.primary_color_hex if export_request else None) or "#0E7490"
    candidate = raw.strip()
    if not re.match(r"^#?[0-9a-fA-F]{6}$", candidate):
        candidate = "#0E7490"
    if not candidate.startswith("#"):
        candidate = f"#{candidate}"
    return colors.HexColor(candidate)


def _with_alpha(color, alpha: float):
    return colors.Color(color.red, color.green, color.blue, alpha=alpha)


def _section_heading(title: str, styles: dict[str, ParagraphStyle]):
    return Paragraph(title, styles["section"])


def _build_evaluation_pdf(
    evaluation: Evaluation,
    profile_snapshot: ProfileSnapshot | None,
    export_request: EvaluationExportRequest | None,
) -> bytes:
    if not REPORTLAB_AVAILABLE or SimpleDocTemplate is None:
        raise RuntimeError("PDF export dependency missing: reportlab is not installed.")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=1.1 * inch,
        bottomMargin=0.7 * inch,
        title="Startup Idea Evaluation Report",
        author=(export_request.company_name if export_request and export_request.company_name else "CRAG AI"),
    )

    meta = _extract_meta_from_dimension_analyses(evaluation.dimension_analyses)
    brand = _resolve_brand_color(export_request)
    brand_soft = _with_alpha(brand, 0.12)
    brand_mid = _with_alpha(brand, 0.2)

    styles = getSampleStyleSheet()
    custom_styles = {
        "brand": ParagraphStyle(
            "brand",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=brand,
            leading=13,
            spaceAfter=6,
        ),
        "title": ParagraphStyle(
            "title",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=24,
            textColor=colors.HexColor("#0B1220"),
            leading=28,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            textColor=colors.HexColor("#4B5563"),
            leading=15,
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=colors.HexColor("#111827"),
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            textColor=colors.HexColor("#1F2937"),
            leading=15,
            spaceAfter=6,
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            textColor=colors.HexColor("#6B7280"),
            leading=13,
        ),
        "pill": ParagraphStyle(
            "pill",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.white,
            alignment=1,
            leading=12,
        ),
    }

    report_title = _safe_paragraph_text(meta.get("idea_title"), "Startup Idea Evaluation Report")
    company_name = _safe_text(export_request.company_name if export_request else None, "CRAG AI")
    company_tagline = _safe_paragraph_text(
        export_request.company_tagline if export_request else None,
        "Evidence-weighted startup idea stress test",
    )
    summary_text = _safe_paragraph_text(meta.get("idea_summary"), "No summary generated for this run.")

    story = []
    story.append(Paragraph(company_name, custom_styles["brand"]))
    story.append(Paragraph(report_title, custom_styles["title"]))
    story.append(Paragraph(company_tagline, custom_styles["subtitle"]))

    verdict = _safe_text(evaluation.verdict, "UNAVAILABLE")
    score = str(evaluation.overall_score) if isinstance(evaluation.overall_score, int) else "N/A"
    confidence = "Low confidence" if evaluation.low_confidence else "Normal confidence"
    created_on = evaluation.created_at.strftime("%b %d, %Y %H:%M") if evaluation.created_at else "-"
    chips = Table(
        [[f"Status: {evaluation.status.upper()}", f"Verdict: {verdict}", f"Score: {score}/100", confidence]],
        colWidths=[1.5 * inch, 1.6 * inch, 1.2 * inch, 2.1 * inch],
    )
    chips.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), brand_soft),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("BOX", (0, 0), (-1, -1), 0.8, brand_mid),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(chips)
    story.append(Spacer(1, 10))

    meta_table = Table(
        [
            ["Evaluation ID", evaluation.id],
            ["Created", created_on],
            ["Startup Type", _safe_text(evaluation.startup_type)],
            ["Market Type", _safe_text(evaluation.market_type)],
        ],
        colWidths=[1.35 * inch, 5.05 * inch],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#374151")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    story.append(_section_heading("Executive Summary", custom_styles))
    story.append(Paragraph(summary_text, custom_styles["body"]))

    story.append(_section_heading("Dimension Scores", custom_styles))
    dimension_rows = [
        ["Market", evaluation.market_score],
        ["Technical", evaluation.technical_score],
        ["Distribution", evaluation.distribution_score],
        ["Founder Fit", evaluation.founder_fit_score],
        ["Timing", evaluation.timing_score],
    ]
    score_table_data = [["Dimension", "Score"]] + [
        [name, f"{value}/100" if isinstance(value, int) else "Unavailable"] for name, value in dimension_rows
    ]
    score_table = Table(score_table_data, colWidths=[3.8 * inch, 2.6 * inch])
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), brand),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]
        )
    )
    story.append(score_table)

    chart_bytes = _decode_image_data_url(export_request.chart_image_data_url if export_request else None)
    if chart_bytes and Image is not None:
        story.append(_section_heading("Score Radar Chart", custom_styles))
        try:
            chart = Image(io.BytesIO(chart_bytes))
            chart.drawHeight = 2.8 * inch
            chart.drawWidth = 2.8 * inch
            chart.hAlign = "LEFT"
            story.append(chart)
        except Exception:
            story.append(Paragraph("Chart could not be rendered from export payload.", custom_styles["muted"]))

    story.append(_section_heading("Top Risks", custom_styles))
    risks = (evaluation.top_risks or [])[:3]
    if not risks:
        story.append(Paragraph("No explicit top risks were returned for this run.", custom_styles["muted"]))
    for idx, risk in enumerate(risks, start=1):
        story.append(Paragraph(f"{idx}. {_safe_paragraph_text(risk)}", custom_styles["body"]))

    story.append(_section_heading("Detailed Dimension Evaluation", custom_styles))
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
        story.append(Paragraph(f"<b>{label}</b>", custom_styles["body"]))
        story.append(Paragraph(_safe_paragraph_text(rationale, "No rationale returned."), custom_styles["body"]))

    story.append(_section_heading("Idea Input", custom_styles))
    story.append(Paragraph(f"<b>Idea Description</b>: {_safe_paragraph_text(evaluation.idea_description)}", custom_styles["body"]))
    if evaluation.problem_statement:
        story.append(
            Paragraph(f"<b>Problem Statement</b>: {_safe_paragraph_text(evaluation.problem_statement)}", custom_styles["body"])
        )
    if evaluation.target_customer:
        story.append(Paragraph(f"<b>Target Customer</b>: {_safe_paragraph_text(evaluation.target_customer)}", custom_styles["body"]))

    story.append(_section_heading("Founder Profile Snapshot", custom_styles))
    profile_data = profile_snapshot.profile_data if profile_snapshot else {}
    if not isinstance(profile_data, dict) or not profile_data:
        story.append(Paragraph("No profile snapshot available for this evaluation.", custom_styles["muted"]))
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
            story.append(
                Paragraph(f"<b>{key.replace('_', ' ').title()}</b>: {_safe_paragraph_text(text)}", custom_styles["body"])
            )

    custom_sections = export_request.custom_sections if export_request and export_request.custom_sections else []
    for section in custom_sections[:8]:
        if not isinstance(section, dict):
            continue
        section_title = _safe_paragraph_text(section.get("title"), "Custom Section")
        section_body = _safe_paragraph_text(section.get("content"), "-")
        story.append(_section_heading(section_title, custom_styles))
        story.append(Paragraph(section_body, custom_styles["body"]))

    if isinstance(evaluation.evidence_sources, list) and evaluation.evidence_sources:
        story.append(_section_heading("Evidence Sources", custom_styles))
        for source in evaluation.evidence_sources[:20]:
            if not isinstance(source, dict):
                continue
            source_title = source.get("title") or source.get("doc_name") or "Untitled source"
            source_url = source.get("source_url") or ""
            detail = _safe_paragraph_text(source_title)
            if source_url:
                detail += f" - {_safe_paragraph_text(source_url)}"
            story.append(Paragraph(detail, custom_styles["body"]))

    def draw_page_decorations(canvas_obj, document):
        width, height = LETTER
        canvas_obj.saveState()
        canvas_obj.setFillColor(brand)
        canvas_obj.rect(0, height - 26, width, 26, stroke=0, fill=1)
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica-Bold", 9)
        canvas_obj.drawString(document.leftMargin, height - 17, company_name.upper())
        canvas_obj.setFillColor(colors.HexColor("#6B7280"))
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawRightString(width - document.rightMargin, 22, f"Page {canvas_obj.getPageNumber()}")
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=draw_page_decorations, onLaterPages=draw_page_decorations)
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
                        "idea_categorization": final_state.get("idea_categorization") or meta.get("idea_categorization"),
                        "idea_summary": final_state.get("idea_summary") or meta.get("idea_summary"),
                        "founder_fit_summary": final_state.get("founder_fit_summary") or meta.get("founder_fit_summary"),
                        "idea_tags": persisted.idea_tags or [],
                        "idea_folder": persisted.idea_folder,
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
                    "idea_categorization": final_state.get("idea_categorization") or meta.get("idea_categorization"),
                    "idea_summary": final_state.get("idea_summary") or meta.get("idea_summary"),
                    "founder_fit_summary": final_state.get("founder_fit_summary") or meta.get("founder_fit_summary"),
                    "idea_tags": persisted.idea_tags or [],
                    "idea_folder": persisted.idea_folder,
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
    tag: str | None = None,
    folder: str | None = None,
    q: str | None = None,
    ai_filter: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_limit = min(max(limit, 1), MAX_HISTORY_LIMIT)
    rows_query = (
        db.query(Evaluation)
        .filter(Evaluation.user_id == current_user.id)
        .order_by(desc(Evaluation.created_at))
    )
    rows = rows_query.limit(safe_limit).all()

    normalized_tag = tag.strip().lower() if isinstance(tag, str) and tag.strip() else None
    normalized_folder = folder.strip().lower() if isinstance(folder, str) and folder.strip() else None
    normalized_query = q.strip().lower() if isinstance(q, str) and q.strip() else None
    ai_tags: list[str] = []
    ai_folder: str | None = None
    if ai_filter and isinstance(q, str) and q.strip():
        ai_tags, ai_folder = parse_filter_tags(q)

    def matches(row: Evaluation) -> bool:
        row_tags = [str(item).strip().lower() for item in (row.idea_tags or [])]
        row_folder = row.idea_folder.strip().lower() if isinstance(row.idea_folder, str) and row.idea_folder.strip() else None

        if normalized_tag and normalized_tag not in row_tags:
            return False
        if normalized_folder and normalized_folder != row_folder:
            return False
        if ai_tags and not any(tag_item in row_tags for tag_item in ai_tags):
            return False
        if ai_folder and row_folder and ai_folder.strip().lower() != row_folder:
            return False
        if normalized_query:
            meta = _extract_meta_from_dimension_analyses(row.dimension_analyses)
            title = str(meta.get("idea_title") or "").strip().lower()
            haystack = " ".join(
                [
                    str(row.idea_description or "").lower(),
                    str(row.target_customer or "").lower(),
                    str(row.problem_statement or "").lower(),
                    row_folder or "",
                    " ".join(row_tags),
                    title,
                ]
            )
            if normalized_query not in haystack and not ai_tags:
                return False
        return True

    filtered = [row for row in rows if matches(row)]
    return [_evaluation_to_payload(row) for row in filtered]


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


@router.get("/{evaluation_id}/keyword-trends")
def get_evaluation_keyword_trends(
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

    payload = build_google_keyword_trends(
        idea_description=evaluation.idea_description,
        target_customer=evaluation.target_customer,
        problem_statement=evaluation.problem_statement,
        startup_type=evaluation.startup_type,
        market_type=evaluation.market_type,
    )
    return payload


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
