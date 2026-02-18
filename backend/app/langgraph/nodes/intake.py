from __future__ import annotations

from app.utils.llm import extract_structured_idea, generate_idea_tags, generate_idea_title

from ..state import EvaluationState


def intake_node(state: EvaluationState) -> EvaluationState:
    idea_description = state["idea_description"]
    target_customer = state.get("target_customer")
    problem_statement = state.get("problem_statement")
    structured = extract_structured_idea(
        idea_description=idea_description,
        target_customer=target_customer,
        problem_statement=problem_statement,
    )
    idea_title = generate_idea_title(
        idea_description=idea_description,
        target_customer=target_customer,
        problem_statement=problem_statement,
    )
    idea_tags, idea_folder = generate_idea_tags(
        idea_description=idea_description,
        target_customer=target_customer,
        problem_statement=problem_statement,
        startup_type=state.get("startup_type"),
        market_type=state.get("market_type"),
    )
    return {
        "structured_idea": structured,
        "idea_title": idea_title,
        "idea_tags": idea_tags,
        "idea_folder": idea_folder,
    }
