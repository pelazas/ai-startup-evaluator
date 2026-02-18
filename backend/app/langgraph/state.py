from __future__ import annotations

from typing import Any, TypedDict


class EvaluationState(TypedDict, total=False):
    idea_description: str
    target_customer: str | None
    problem_statement: str | None
    startup_type: str | None
    market_type: str | None
    web_enabled: bool
    idea_tags: list[str]
    idea_folder: str | None
    profile_data: dict[str, Any]
    evaluation_id: str

    structured_idea: dict[str, Any]
    idea_title: str
    idea_categorization: dict[str, str]
    idea_summary: str
    founder_fit_summary: str
    internal_retrieved_chunks: list[dict[str, Any]]
    web_retrieved_chunks: list[dict[str, Any]]
    web_queries_used: list[str]
    retrieved_chunks: list[dict[str, Any]]
    dimension_evidence_map: dict[str, list[dict[str, Any]]]
    dimension_scores: dict[str, int | None]
    dimension_analyses: dict[str, dict[str, Any]]
    failed_dimensions: list[str]
    parse_diagnostics: list[str]
    top_risks: list[str]
    low_confidence: bool

    overall_score: int | None
    verdict: str | None
    evidence_sources: list[dict[str, Any]]
    evidence_mix: dict[str, Any]
