from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from app.config import settings
from app.services.web_search_service import web_search
from app.utils.llm import generate_search_keywords

LOGGER = logging.getLogger(__name__)

MONTHS_BACK = 12
MAX_KEYWORDS = 4
CACHE_TTL = timedelta(hours=24)

_CACHE: dict[str, tuple[datetime, dict[str, Any]]] = {}


def _growth_percent(points: list[dict[str, Any]]) -> float | None:
    values = [point["value"] for point in points if isinstance(point.get("value"), int)]
    if len(values) < 6:
        return None
    window = min(4, len(values) // 2)
    early = values[:window]
    recent = values[-window:]
    early_avg = sum(early) / len(early) if early else 0
    recent_avg = sum(recent) / len(recent) if recent else 0
    if early_avg <= 0:
        return None
    return round(((recent_avg - early_avg) / early_avg) * 100, 1)


def _month_start(dt: date) -> date:
    return date(dt.year, dt.month, 1)


def _next_month(dt: date) -> date:
    if dt.month == 12:
        return date(dt.year + 1, 1, 1)
    return date(dt.year, dt.month + 1, 1)


def _month_windows(count: int) -> list[tuple[date, date]]:
    current = _month_start(date.today())
    windows: list[tuple[date, date]] = []
    for _ in range(count):
        start = current
        end = _next_month(start) - timedelta(days=1)
        windows.append((start, end))
        current = date(start.year - 1, 12, 1) if start.month == 1 else date(start.year, start.month - 1, 1)
    return list(reversed(windows))


def _query_for_window(keyword: str, start: date, end: date) -> str:
    return f"{keyword} worldwide demand {start.isoformat()} to {end.isoformat()} web trend volume"


def _window_volume(keyword: str, start: date, end: date) -> tuple[int, bool]:
    results = web_search(_query_for_window(keyword, start, end), max_results=15)
    success = isinstance(results, list)
    unique_sources = {
        str(
            (
                (item.get("metadata") if isinstance(item.get("metadata"), dict) else {}).get("source_url")
                or item.get("id")
                or ""
            )
        )
        for item in results
        if isinstance(item, dict)
    }
    unique_sources = {item for item in unique_sources if item}
    return len(unique_sources), success


def _normalize_manual_keywords(raw: str | None) -> list[str]:
    if not isinstance(raw, str) or not raw.strip():
        return []
    parts = [" ".join(item.strip().lower().split()) for item in raw.split(",")]
    cleaned: list[str] = []
    for part in parts:
        if not part or len(part) < 3:
            continue
        part = " ".join(part.split()[:2])
        if part not in cleaned:
            cleaned.append(part)
    return cleaned[:MAX_KEYWORDS]


def _cache_key(*, keywords: list[str], timeframe: str, location: str, source: str) -> str:
    return f"{source}|{location}|{timeframe}|{'|'.join(keywords)}"


def _status_payload(
    *,
    status: str,
    error_code: str,
    details: str,
    keywords: list[str],
    series: list[dict[str, Any]] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "error_code": error_code,
        "details": details,
        "keywords": keywords,
        "selected_keyword": keywords[0] if keywords else None,
        "series": series or [],
        "timeframe": "past 12 months",
        "location": "worldwide",
        "source": "web_search",
        "metric": "absolute_web_mentions",
        "generated_at": date.today().isoformat(),
        "diagnostics": diagnostics or {},
    }


def build_google_keyword_trends(
    *,
    idea_description: str,
    target_customer: str | None,
    problem_statement: str | None,
    startup_type: str | None,
    market_type: str | None,
    keyword_override: str | None = None,
) -> dict[str, Any]:
    manual_keywords = _normalize_manual_keywords(keyword_override)
    extracted_keywords = generate_search_keywords(
        idea_description=idea_description,
        target_customer=target_customer,
        problem_statement=problem_statement,
        startup_type=startup_type,
        market_type=market_type,
    )[:MAX_KEYWORDS]
    keywords = manual_keywords or extracted_keywords

    diagnostics: dict[str, Any] = {
        "manual_override_used": bool(manual_keywords),
        "extracted_keywords_count": len(extracted_keywords),
        "provider_success_count": 0,
        "provider_fail_count": 0,
        "series_count": 0,
        "point_count": 0,
    }
    LOGGER.info(
        "keyword_trends keywords extracted=%s manual_override=%s final=%s",
        len(extracted_keywords),
        bool(manual_keywords),
        len(keywords),
    )

    if not settings.web_search_enabled or not settings.tavily_api_key:
        return _status_payload(
            status="provider_error",
            error_code="KWT_PROVIDER_UNAVAILABLE",
            details="Trend provider is not available in this environment.",
            keywords=keywords,
            diagnostics=diagnostics,
        )

    if not keywords:
        return _status_payload(
            status="no_keywords",
            error_code="KWT_NO_KEYWORDS",
            details="No usable keywords were extracted automatically.",
            keywords=[],
            diagnostics=diagnostics,
        )

    timeframe = "past 12 months"
    location = "worldwide"
    source = "web_search"
    cache_key = _cache_key(keywords=keywords, timeframe=timeframe, location=location, source=source)
    now = datetime.utcnow()
    cached = _CACHE.get(cache_key)
    if cached and now - cached[0] < CACHE_TTL:
        payload = dict(cached[1])
        payload["details"] = f"{payload.get('details', 'Loaded')} (cached)."
        return payload

    windows = _month_windows(MONTHS_BACK)
    keyword_series: list[dict[str, Any]] = []
    for keyword in keywords:
        points: list[dict[str, Any]] = []
        for start, end in windows:
            monthly_volume, success = _window_volume(keyword, start, end)
            if success:
                diagnostics["provider_success_count"] += 1
            else:
                diagnostics["provider_fail_count"] += 1
            points.append({"date": start.isoformat(), "value": monthly_volume})

        total_volume = sum(point["value"] for point in points)
        latest_volume = points[-1]["value"] if points else 0
        growth = _growth_percent(points)
        keyword_series.append(
            {
                "keyword": keyword,
                "volume": total_volume,
                "latest_volume": latest_volume,
                "growth_percent": growth,
                "points": points,
            }
        )

    diagnostics["series_count"] = len(keyword_series)
    diagnostics["point_count"] = sum(len(series.get("points", [])) for series in keyword_series)
    LOGGER.info(
        "keyword_trends provider success=%s fail=%s series=%s points=%s",
        diagnostics["provider_success_count"],
        diagnostics["provider_fail_count"],
        diagnostics["series_count"],
        diagnostics["point_count"],
    )

    if not keyword_series:
        payload = _status_payload(
            status="no_trends_data",
            error_code="KWT_NO_TRENDS_DATA",
            details="No trend data was returned for the extracted keywords.",
            keywords=keywords,
            diagnostics=diagnostics,
        )
        _CACHE[cache_key] = (now, payload)
        return payload

    selected_keyword = keyword_series[0]["keyword"]
    payload = {
        "status": "ok",
        "error_code": "KWT_OK",
        "details": "Trend data loaded successfully.",
        "keywords": [item["keyword"] for item in keyword_series],
        "selected_keyword": selected_keyword,
        "series": keyword_series,
        "timeframe": timeframe,
        "location": location,
        "source": source,
        "metric": "absolute_web_mentions",
        "generated_at": date.today().isoformat(),
        "diagnostics": diagnostics,
    }
    _CACHE[cache_key] = (now, payload)
    return payload
