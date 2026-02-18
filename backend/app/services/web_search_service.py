from __future__ import annotations

import logging
from typing import Any

import requests
from requests import HTTPError, RequestException, Timeout

from app.config import settings

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
LOGGER = logging.getLogger(__name__)


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
        LOGGER.debug("Web search skipped: WEB_SEARCH_ENABLED is false.")
        return []
    if not settings.tavily_api_key:
        LOGGER.warning("Web search unavailable: TAVILY_API_KEY is not configured.")
        return []

    normalized_query = _normalize_query(query)
    if not normalized_query:
        LOGGER.debug("Web search skipped: empty normalized query.")
        return []

    requested_results = max(1, min(max_results or settings.web_search_max_results, 15))
    payload = {
        "api_key": settings.tavily_api_key,
        "query": normalized_query,
        "search_depth": "advanced",
        "max_results": requested_results,
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
            LOGGER.warning(
                "Web search returned unexpected payload shape (missing results list). query=%r status=%s",
                normalized_query[:120],
                response.status_code,
            )
            return []
        chunks = [_to_web_chunk(item) for item in results if isinstance(item, dict)]
        filtered_chunks = [chunk for chunk in chunks if chunk.get("content")]
        if not filtered_chunks:
            LOGGER.warning(
                "Web search returned no usable content. query=%r raw_results=%d requested_results=%d",
                normalized_query[:120],
                len(results),
                requested_results,
            )
        else:
            LOGGER.info(
                "Web search success. query=%r usable_results=%d raw_results=%d",
                normalized_query[:120],
                len(filtered_chunks),
                len(results),
            )
        return filtered_chunks
    except Timeout:
        LOGGER.exception(
            "Web search timeout. query=%r timeout_seconds=%d",
            normalized_query[:120],
            max(2, settings.web_search_timeout_seconds),
        )
        return []
    except HTTPError:
        status_code = getattr(response, "status_code", "unknown") if "response" in locals() else "unknown"
        response_preview = ""
        if "response" in locals():
            try:
                response_preview = (response.text or "")[:300]
            except Exception:
                response_preview = ""
        LOGGER.exception(
            "Web search HTTP error. query=%r status=%s body_preview=%r",
            normalized_query[:120],
            status_code,
            response_preview,
        )
        return []
    except RequestException:
        LOGGER.exception("Web search request error. query=%r", normalized_query[:120])
        return []
    except ValueError:
        LOGGER.exception("Web search JSON decode error. query=%r", normalized_query[:120])
        return []
    except Exception:
        LOGGER.exception("Unexpected web search failure. query=%r", normalized_query[:120])
        return []
