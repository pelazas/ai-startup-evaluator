from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import time
from pathlib import Path

import requests

YC_COMPANIES_URL = "https://www.ycombinator.com/companies"
YC_COMPANY_URL_TEMPLATE = "https://www.ycombinator.com/companies/{slug}"
ALGOLIA_PREFIX = "window.AlgoliaOpts = "
DEFAULT_INDEX = "YCCompany_By_Launch_Date_production"
DATA_PAGE_PATTERN = re.compile(r'data-page="([^"]+)"')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape YC active founder profiles from companies sorted by launch date."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown file path. Defaults to backend/raw_documents/yc_active_founders_<timestamp>.md",
    )
    parser.add_argument("--index", default=DEFAULT_INDEX, help="Algolia index name.")
    parser.add_argument("--hits-per-page", type=int, default=20, help="Algolia hits per page.")
    parser.add_argument("--max-windows", type=int, default=None, help="Optional pagination window cap for testing.")
    parser.add_argument("--max-companies", type=int, default=None, help="Optional company cap for testing.")
    parser.add_argument("--sleep-seconds", type=float, default=0.05, help="Delay between requests.")
    return parser.parse_args()


def _with_retry(label: str, fn):
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(0.5 * attempt)
    raise RuntimeError(f"{label} failed after retries: {last_exc}")


def load_algolia_opts(session: requests.Session) -> dict:
    response = session.get(YC_COMPANIES_URL, timeout=30)
    response.raise_for_status()
    source = response.text

    marker = source.find(ALGOLIA_PREFIX)
    if marker == -1:
        raise RuntimeError("Algolia config marker not found on YC companies page.")
    start = marker + len(ALGOLIA_PREFIX)
    end = source.find("};", start)
    if end == -1:
        raise RuntimeError("Could not parse Algolia config boundaries.")
    return json.loads(source[start : end + 1])


def fetch_company_hits(
    session: requests.Session,
    *,
    app_id: str,
    api_key: str,
    index_name: str,
    hits_per_page: int,
    launched_before: int | None,
) -> list[dict]:
    url = f"https://{app_id}-dsn.algolia.net/1/indexes/{index_name}/query"
    headers = {
        "X-Algolia-Application-Id": app_id,
        "X-Algolia-API-Key": api_key,
        "Content-Type": "application/json",
    }

    params = f"query=&hitsPerPage={hits_per_page}&page=0"
    if launched_before is not None:
        params += f"&numericFilters=launched_at<{launched_before}"

    first_page = _with_retry(
        "algolia first page",
        lambda: session.post(url, headers=headers, json={"params": params}, timeout=30),
    )
    first_page.raise_for_status()
    payload = first_page.json()
    hits = list(payload.get("hits", []))
    nb_pages = int(payload.get("nbPages", 0))

    for page in range(1, nb_pages):
        page_params = f"query=&hitsPerPage={hits_per_page}&page={page}"
        if launched_before is not None:
            page_params += f"&numericFilters=launched_at<{launched_before}"
        page_resp = _with_retry(
            f"algolia page {page}",
            lambda: session.post(url, headers=headers, json={"params": page_params}, timeout=30),
        )
        page_resp.raise_for_status()
        hits.extend(page_resp.json().get("hits", []))
    return hits


def fetch_launch_sorted_companies(
    session: requests.Session,
    *,
    app_id: str,
    api_key: str,
    index_name: str,
    hits_per_page: int,
    max_windows: int | None,
    max_companies: int | None,
    sleep_seconds: float,
) -> list[dict]:
    companies: list[dict] = []
    launched_before: int | None = None
    windows = 0

    while True:
        window_hits = fetch_company_hits(
            session,
            app_id=app_id,
            api_key=api_key,
            index_name=index_name,
            hits_per_page=hits_per_page,
            launched_before=launched_before,
        )
        if not window_hits:
            break

        companies.extend(window_hits)
        windows += 1

        launch_values = [h.get("launched_at") for h in window_hits if isinstance(h.get("launched_at"), (int, float))]
        if not launch_values:
            break
        launched_before = int(min(launch_values)) - 1

        if max_windows is not None and windows >= max_windows:
            break
        if max_companies is not None and len(companies) >= max_companies:
            companies = companies[:max_companies]
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    companies.sort(
        key=lambda item: (
            item.get("launched_at") is not None,
            item.get("launched_at") if item.get("launched_at") is not None else -1,
        ),
        reverse=True,
    )
    return companies


def extract_company_page_data(company_html: str) -> dict | None:
    match = DATA_PAGE_PATTERN.search(company_html)
    if not match:
        return None
    raw = html.unescape(match.group(1))
    parsed = json.loads(raw)
    return parsed.get("props", {}).get("company")


def extract_active_founders(company_data: dict) -> list[dict]:
    founders = company_data.get("founders", []) if company_data else []
    result: list[dict] = []
    for founder in founders:
        if not founder.get("is_active", False):
            continue
        result.append(
            {
                "full_name": founder.get("full_name") or "",
                "title": founder.get("title") or "",
                "founder_bio": founder.get("founder_bio") or "",
                "twitter_url": founder.get("twitter_url") or "",
                "linkedin_url": founder.get("linkedin_url") or "",
                "latest_yc_company": founder.get("latest_yc_company") or "",
            }
        )
    return result


def launched_iso(value) -> str:
    if not isinstance(value, (int, float)):
        return "N/A"
    return dt.datetime.fromtimestamp(int(value), tz=dt.timezone.utc).isoformat()


def write_markdown(output_path: Path, records: list[dict]) -> None:
    generated = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    lines = [
        "# YC Active Founders Raw Export",
        "",
        f"- Source: {YC_COMPANIES_URL} (launch-date order)",
        f"- Generated At (UTC): {generated}",
        f"- Total Companies Processed: {len(records)}",
        "",
    ]

    for idx, company in enumerate(records, start=1):
        lines.append(f"## {idx}. {company.get('name') or 'Unknown'}")
        lines.append("")
        lines.append(f"- Slug: {company.get('slug') or 'N/A'}")
        lines.append(f"- Launch Timestamp: {company.get('launched_at') if company.get('launched_at') is not None else 'N/A'}")
        lines.append(f"- Launch ISO: {launched_iso(company.get('launched_at'))}")
        lines.append(f"- Company Description: {company.get('description') or 'N/A'}")
        lines.append(f"- Active Founders Count: {len(company.get('active_founders', []))}")
        lines.append("")
        for founder in company.get("active_founders", []):
            lines.append(f"### Founder: {founder.get('full_name') or 'Unknown'}")
            lines.append(f"- Title: {founder.get('title') or 'N/A'}")
            lines.append(f"- Founder Description: {founder.get('founder_bio') or 'N/A'}")
            lines.append(f"- Twitter: {founder.get('twitter_url') or 'N/A'}")
            lines.append(f"- LinkedIn: {founder.get('linkedin_url') or 'N/A'}")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    backend_root = Path(__file__).resolve().parents[1]
    timestamp = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = (
        Path(args.output).resolve()
        if args.output
        else backend_root / "raw_documents" / f"yc_active_founders_{timestamp}.md"
    )

    with requests.Session() as session:
        opts = load_algolia_opts(session)
        companies = fetch_launch_sorted_companies(
            session,
            app_id=opts["app"],
            api_key=opts["key"],
            index_name=args.index,
            hits_per_page=args.hits_per_page,
            max_windows=args.max_windows,
            max_companies=args.max_companies,
            sleep_seconds=args.sleep_seconds,
        )

        records: list[dict] = []
        for company in companies:
            slug = company.get("slug")
            if not slug:
                continue
            page_url = YC_COMPANY_URL_TEMPLATE.format(slug=slug)
            response = _with_retry(f"company page {slug}", lambda: session.get(page_url, timeout=30))
            response.raise_for_status()
            company_data = extract_company_page_data(response.text)
            active_founders = extract_active_founders(company_data or {})
            records.append(
                {
                    "name": company.get("name") or "",
                    "slug": slug,
                    "launched_at": company.get("launched_at"),
                    "description": (company.get("one_liner") or company.get("long_description") or "").strip(),
                    "active_founders": active_founders,
                }
            )
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    write_markdown(output_path, records)
    print(f"[done] wrote {len(records)} companies with active founder profiles to {output_path}")


if __name__ == "__main__":
    main()
