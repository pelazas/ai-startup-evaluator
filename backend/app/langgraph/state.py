from __future__ import annotations

from typing import Any, TypedDict


class EvaluationState(TypedDict, total=False):
    idea_description: str
    target_customer: str | None
    problem_statement: str | None
    startup_type: str | None
    market_type: str | None
    profile_data: dict[str, Any]
    evaluation_id: str

    structured_idea: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    dimension_scores: dict[str, int | None]
    dimension_analyses: dict[str, dict[str, Any]]
    top_risks: list[str]
    low_confidence: bool

    overall_score: int
    verdict: str
    evidence_sources: list[dict[str, Any]]

