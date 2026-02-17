from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.vector_collection import (
    AIMarketDataDoc,
    FounderPrinciplesDoc,
    PersonalProfileDoc,
    StartupExamplesDoc,
    TechnicalConstraintsDoc,
)

COLLECTION_MODELS = {
    "founder_principles": FounderPrinciplesDoc,
    "ai_market_data": AIMarketDataDoc,
    "startup_examples": StartupExamplesDoc,
    "technical_constraints": TechnicalConstraintsDoc,
    "personal_profile": PersonalProfileDoc,
}


def _retrieval_reason(source: str, meta: dict[str, Any]) -> str:
    if source == "vector":
        base = "Retrieved by semantic similarity to the submitted idea."
    else:
        base = "Retrieved by keyword overlap with the submitted idea."
    section = meta.get("section")
    if isinstance(section, str) and section.strip():
        return f"{base} Section: {section.strip()}."
    return base


def _serialize_doc(collection: str, row: Any, source: str) -> dict[str, Any]:
    meta = row.doc_metadata if isinstance(row.doc_metadata, dict) else {}
    return {
        "id": str(row.id),
        "content": row.content,
        "collection": collection,
        "source": meta.get("source", source),
        "title": meta.get("title"),
        "metadata": meta,
        "retrieval_method": source,
        "retrieval_reason": _retrieval_reason(source, meta),
    }


def _keyword_query(text: str) -> str:
    return " ".join(part.strip() for part in text.split() if part.strip())[:200]


def hybrid_search_collection(
    db: Session,
    collection: str,
    embedding: list[float],
    keyword_text: str,
    per_collection_limit: int = 10,
) -> list[dict[str, Any]]:
    model = COLLECTION_MODELS[collection]

    vector_stmt = select(model).order_by(model.embedding.cosine_distance(embedding)).limit(per_collection_limit)
    vector_rows = db.execute(vector_stmt).scalars().all()

    keyword_rows: Sequence[Any] = []
    cleaned_query = _keyword_query(keyword_text)
    if cleaned_query:
        keyword_stmt = (
            select(model)
            .where(model.content_tsvector.op("@@")(func.plainto_tsquery("english", cleaned_query)))
            .limit(per_collection_limit)
        )
        keyword_rows = db.execute(keyword_stmt).scalars().all()

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in vector_rows:
        key = str(row.id)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        merged.append(_serialize_doc(collection, row, source="vector"))
    for row in keyword_rows:
        key = str(row.id)
        if key in seen_ids:
            continue
        seen_ids.add(key)
        merged.append(_serialize_doc(collection, row, source="keyword"))

    return merged[:per_collection_limit]


def hybrid_search_all_collections(
    db: Session,
    embedding: list[float],
    keyword_text: str,
    per_collection_limit: int = 10,
) -> list[dict[str, Any]]:
    all_chunks: list[dict[str, Any]] = []
    for collection in COLLECTION_MODELS:
        all_chunks.extend(
            hybrid_search_collection(
                db=db,
                collection=collection,
                embedding=embedding,
                keyword_text=keyword_text,
                per_collection_limit=per_collection_limit,
            )
        )
    return all_chunks
