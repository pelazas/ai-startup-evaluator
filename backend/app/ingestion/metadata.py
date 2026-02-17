from __future__ import annotations

import hashlib
from pathlib import Path


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_document_id(source: str, content_hash: str) -> str:
    stem = Path(source).stem.replace(" ", "_").replace("-", "_").lower()
    return f"{stem}_{content_hash[:10]}"


def build_metadata(
    *,
    source: str,
    title: str,
    file_type: str,
    collection: str | None,
    confidence: float,
    content_hash: str,
    section_count: int,
    classification_reason: str,
) -> dict:
    return {
        "source": source,
        "title": title,
        "file_type": file_type,
        "collection": collection,
        "classification_confidence": round(confidence, 4),
        "classification_reason": classification_reason,
        "content_hash": content_hash,
        "section_count": section_count,
    }
