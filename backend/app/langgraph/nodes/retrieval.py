from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.retrieval_service import hybrid_search_all_collections
from app.utils.embeddings import embed_text

from ..state import EvaluationState


def retrieval_node(state: EvaluationState, db: Session) -> EvaluationState:
    query_text = " ".join(
        [
            state["idea_description"],
            state.get("target_customer") or "",
            state.get("problem_statement") or "",
        ]
    ).strip()
    query_embedding = embed_text(query_text)
    chunks = hybrid_search_all_collections(db=db, embedding=query_embedding, keyword_text=query_text, per_collection_limit=10)
    low_confidence = len(chunks) < 20
    return {
        "retrieved_chunks": chunks,
        "low_confidence": low_confidence,
    }

