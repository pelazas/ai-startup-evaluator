from __future__ import annotations

import logging
import time
from typing import Any

import requests
from requests import HTTPError, RequestException, Timeout

from app.config import settings

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
LOGGER = logging.getLogger(__name__)
_CACHE: dict[tuple[str, int], tuple[float, list[dict[str, Any]]]] = {}


def _normalize_query(query: str) -> str:
    normalized = " ".join(query.split()).strip()
    # Strip highly-specific date spans that often hurt recall and increase timeout risk.
    normalized = normalized.replace("to 2025-10-31", "").replace("to 2025-11-30", "").replace("to 2025-12-31", "")
    normalized = normalized.replace("to 2026-01-31", "").replace("to 2026-02-28", "")
    return normalized[:300]


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
    cache_ttl = max(60, settings.web_search_cache_ttl_seconds)
    cache_key = (normalized_query.lower(), requested_results)
    cached = _CACHE.get(cache_key)
    now = time.time()
    if cached and cached[0] > now:
        LOGGER.debug("Web search cache hit. query=%r results=%d", normalized_query[:120], requested_results)
        return cached[1]

    max_attempts = max(1, settings.web_search_retry_attempts + 1)
    timeout_seconds = max(2, settings.web_search_timeout_seconds)
    connect_timeout = min(3, timeout_seconds)
    read_timeout = max(2, timeout_seconds - connect_timeout)

    for attempt in range(1, max_attempts + 1):
        depth = settings.web_search_search_depth if attempt == 1 else "basic"
        per_attempt_results = requested_results if attempt == 1 else max(3, requested_results // 2)
        payload = {
            "api_key": settings.tavily_api_key,
            "query": normalized_query,
            "search_depth": depth,
            "max_results": per_attempt_results,
            "include_answer": False,
            "include_images": False,
        }
        try:
            response = requests.post(
                TAVILY_SEARCH_URL,
                json=payload,
                timeout=(connect_timeout, read_timeout),
            )
            response.raise_for_status()
            body = response.json()
            results = body.get("results")
            if not isinstance(results, list):
                LOGGER.warning(
                    "Web search unexpected payload. query=%r status=%s attempt=%d",
                    normalized_query[:120],
                    response.status_code,
                    attempt,
                )
                return []
            chunks = [_to_web_chunk(item) for item in results if isinstance(item, dict)]
            filtered_chunks = [chunk for chunk in chunks if chunk.get("content")]
            if filtered_chunks:
                _CACHE[cache_key] = (time.time() + cache_ttl, filtered_chunks)
                LOGGER.info(
                    "Web search success. query=%r usable_results=%d raw_results=%d attempt=%d",
                    normalized_query[:120],
                    len(filtered_chunks),
                    len(results),
                    attempt,
                )
                return filtered_chunks
            LOGGER.warning(
                "Web search returned no usable content. query=%r raw_results=%d attempt=%d",
                normalized_query[:120],
                len(results),
                attempt,
            )
            return []
        except Timeout:
            LOGGER.warning(
                "Web search timeout. query=%r attempt=%d/%d timeout=%ss",
                normalized_query[:120],
                attempt,
                max_attempts,
                timeout_seconds,
            )
            if attempt < max_attempts:
                time.sleep(0.35 * attempt)
                continue
            return []
        except HTTPError:
            status_code = getattr(response, "status_code", "unknown") if "response" in locals() else "unknown"
            LOGGER.warning(
                "Web search HTTP error. query=%r status=%s attempt=%d/%d",
                normalized_query[:120],
                status_code,
                attempt,
                max_attempts,
            )
            return []
        except RequestException:
            LOGGER.warning(
                "Web search request error. query=%r attempt=%d/%d",
                normalized_query[:120],
                attempt,
                max_attempts,
            )
            if attempt < max_attempts:
                time.sleep(0.35 * attempt)
                continue
            return []
        except ValueError:
            LOGGER.warning("Web search JSON decode error. query=%r", normalized_query[:120])
            return []
        except Exception:
            LOGGER.warning("Unexpected web search failure. query=%r", normalized_query[:120])
            return []
    return []
