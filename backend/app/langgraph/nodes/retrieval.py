from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.retrieval_service import hybrid_search_all_collections
from app.utils.embeddings import embed_text

from ..state import EvaluationState

LOGGER = logging.getLogger(__name__)


def retrieval_node(state: EvaluationState, db: Session) -> EvaluationState:
    query_text = " ".join(
        [
            state["idea_description"],
            state.get("target_customer") or "",
            state.get("problem_statement") or "",
        ]
    ).strip()
    query_embedding = embed_text(query_text)
    try:
        chunks = hybrid_search_all_collections(db=db, embedding=query_embedding, keyword_text=query_text, per_collection_limit=10)
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Internal retrieval failed for evaluation_id=%s", state.get("evaluation_id"))
        diagnostics = list(state.get("parse_diagnostics", []))
        diagnostics.append(f"retrieval_error:{type(exc).__name__}")
        return {
            "internal_retrieved_chunks": [],
            "web_retrieved_chunks": [],
            "web_queries_used": [],
            "retrieved_chunks": [],
            "low_confidence": True,
            "parse_diagnostics": diagnostics,
        }

    low_confidence = len(chunks) < 20
    return {
        "internal_retrieved_chunks": chunks,
        "web_retrieved_chunks": [],
        "web_queries_used": [],
        "retrieved_chunks": chunks,
        "low_confidence": low_confidence,
    }
