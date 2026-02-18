from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.web_search_service import web_search
from app.utils.llm import generate_search_keywords

MONTHS_BACK = 12
MAX_KEYWORDS = 3


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
    return (
        f"{keyword} worldwide market demand "
        f"{start.isoformat()} to {end.isoformat()} trend volume"
    )


def _window_volume(keyword: str, start: date, end: date) -> int:
    results = web_search(_query_for_window(keyword, start, end), max_results=15)
    unique_sources = {
        str(((item.get("metadata") if isinstance(item.get("metadata"), dict) else {}).get("source_url") or item.get("id") or ""))
        for item in results
        if isinstance(item, dict)
    }
    unique_sources = {item for item in unique_sources if item}
    return len(unique_sources)


def build_google_keyword_trends(
    *,
    idea_description: str,
    target_customer: str | None,
    problem_statement: str | None,
    startup_type: str | None,
    market_type: str | None,
) -> dict[str, Any]:
    keywords = generate_search_keywords(
        idea_description=idea_description,
        target_customer=target_customer,
        problem_statement=problem_statement,
        startup_type=startup_type,
        market_type=market_type,
    )[:MAX_KEYWORDS]

    if not keywords:
        return {"keywords": [], "series": [], "error": "No valid keywords could be extracted."}

    windows = _month_windows(MONTHS_BACK)
    keyword_series: list[dict[str, Any]] = []
    for keyword in keywords:
        points: list[dict[str, Any]] = []
        for start, end in windows:
            monthly_volume = _window_volume(keyword, start, end)
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

    if not keyword_series:
        return {
            "keywords": keywords,
            "series": [],
            "error": "No web trend volume data available for extracted keywords.",
        }

    selected_keyword = keyword_series[0]["keyword"]
    return {
        "keywords": [item["keyword"] for item in keyword_series],
        "selected_keyword": selected_keyword,
        "series": keyword_series,
        "timeframe": "past 12 months",
        "location": "worldwide",
        "source": "web_search",
        "metric": "absolute_web_mentions",
        "generated_at": date.today().isoformat(),
    }
