from __future__ import annotations

from app.utils.llm import extract_structured_idea

from ..state import EvaluationState


def intake_node(state: EvaluationState) -> EvaluationState:
    structured = extract_structured_idea(
        idea_description=state["idea_description"],
        target_customer=state.get("target_customer"),
        problem_statement=state.get("problem_statement"),
    )
    return {"structured_idea": structured}

