from __future__ import annotations

from typing import Any

import requests

from app.config import settings

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def _normalize_query(query: str) -> str:
    return " ".join(query.split()).strip()[:500]


def _to_web_chunk(item: dict[str, Any]) -> dict[str, Any]:
    title = item.get("title")
    url = item.get("url")
    content = item.get("content")
    published_at = item.get("published_date")

    chunk_id = None
    if isinstance(url, str) and url.strip():
        chunk_id = f"web::{url.strip()}"
    elif isinstance(title, str) and title.strip():
        chunk_id = f"web::{title.strip().lower()}"

    return {
        "id": chunk_id or "web::unknown",
        "content": content if isinstance(content, str) else "",
        "collection": "web",
        "source": "tavily",
        "title": title if isinstance(title, str) and title.strip() else "Untitled web source",
        "metadata": {
            "source_name": item.get("source") if isinstance(item.get("source"), str) else "Web",
            "source_url": url if isinstance(url, str) and url.strip() else None,
            "published_at": published_at if isinstance(published_at, str) and published_at.strip() else None,
        },
        "retrieval_method": "web_search",
        "retrieval_reason": "Retrieved from live web search for current market/context evidence.",
    }


def web_search(query: str, max_results: int | None = None) -> list[dict[str, Any]]:
    if not settings.web_search_enabled:
        return []
    if not settings.tavily_api_key:
        return []

    normalized_query = _normalize_query(query)
    if not normalized_query:
        return []

    payload = {
        "api_key": settings.tavily_api_key,
        "query": normalized_query,
        "search_depth": "advanced",
        "max_results": max(1, min(max_results or settings.web_search_max_results, 15)),
        "include_answer": False,
        "include_images": False,
    }
    try:
        response = requests.post(
            TAVILY_SEARCH_URL,
            json=payload,
            timeout=max(2, settings.web_search_timeout_seconds),
        )
        response.raise_for_status()
        body = response.json()
        results = body.get("results")
        if not isinstance(results, list):
            return []
        chunks = [_to_web_chunk(item) for item in results if isinstance(item, dict)]
        return [chunk for chunk in chunks if chunk.get("content")]
    except Exception:
        return []
