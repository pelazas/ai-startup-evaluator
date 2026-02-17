from __future__ import annotations

import requests

from app.config import settings

COHERE_EMBED_MODEL = "embed-english-v3.0"
EMBEDDING_DIMENSION = 1024


def _zero_embedding() -> list[float]:
    return [0.0] * EMBEDDING_DIMENSION


def embed_text(text: str) -> list[float]:
    api_key = settings.cohere_api_key
    if not api_key:
        return _zero_embedding()

    url = "https://api.cohere.com/v1/embed"
    payload = {
        "texts": [text],
        "model": COHERE_EMBED_MODEL,
        "input_type": "search_query",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        body = response.json()
        embeddings = body.get("embeddings")
        if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
            vector = embeddings[0]
            if len(vector) == EMBEDDING_DIMENSION:
                return [float(item) for item in vector]
    except Exception:
        return _zero_embedding()

    return _zero_embedding()

