from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.langgraph.nodes.critic import critic_node
from app.langgraph.nodes.intake import intake_node
from app.langgraph.nodes.retrieval import retrieval_node
from app.langgraph.nodes.web_retrieval import web_retrieval_node
from app.langgraph.nodes.verdict import verdict_node
from app.langgraph.state import EvaluationState

try:
    from langgraph.graph import StateGraph
except Exception:  # pragma: no cover
    StateGraph = None


class _FallbackCompiledGraph:
    def __init__(self, db: Session):
        self.db = db

    def stream(self, state: EvaluationState):
        intake_update = intake_node(state)
        yield {"intake": intake_update}
        retrieval_input = dict(state)
        retrieval_input.update(intake_update)
        retrieval_update = retrieval_node(retrieval_input, self.db)
        yield {"retrieval": retrieval_update}
        web_retrieval_input = dict(retrieval_input)
        web_retrieval_input.update(retrieval_update)
        web_retrieval_update = web_retrieval_node(web_retrieval_input)
        yield {"web_retrieval": web_retrieval_update}
        critic_input = dict(web_retrieval_input)
        critic_input.update(web_retrieval_update)
        critic_update = critic_node(critic_input)
        yield {"critic": critic_update}
        verdict_input = dict(critic_input)
        verdict_input.update(critic_update)
        verdict_update = verdict_node(verdict_input)
        yield {"verdict": verdict_update}


def build_evaluation_graph(db: Session) -> Any:
    if StateGraph is None:
        return _FallbackCompiledGraph(db)

    graph = StateGraph(EvaluationState)

    graph.add_node("intake", intake_node)
    graph.add_node("retrieval", lambda state: retrieval_node(state, db))
    graph.add_node("web_retrieval", web_retrieval_node)
    graph.add_node("critic", critic_node)
    # Avoid collision with the "verdict" state field.
    graph.add_node("verdict_step", verdict_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "retrieval")
    graph.add_edge("retrieval", "web_retrieval")
    graph.add_edge("web_retrieval", "critic")
    graph.add_edge("critic", "verdict_step")
    graph.set_finish_point("verdict_step")

    return graph.compile()
