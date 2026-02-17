from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

import requests

YC_COMPANIES_URL = "https://www.ycombinator.com/companies"
ALGOLIA_PREFIX = "window.AlgoliaOpts = "
DEFAULT_INDEX = "YCCompany_By_Launch_Date_production"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape YC companies from the public directory and write raw markdown output."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown file path. Defaults to backend/raw_documents/yc_companies_launch_date_<timestamp>.md",
    )
    parser.add_argument("--index", default=DEFAULT_INDEX, help="Algolia index name.")
    parser.add_argument("--hits-per-page", type=int, default=20, help="Algolia hits per page.")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional window cap for testing.")
    parser.add_argument(
        "--sort",
        choices=["desc", "asc"],
        default="desc",
        help="Launch date order. desc uses YC launch-date index order; asc reverses in output.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=0.05, help="Delay between page requests.")
    return parser.parse_args()


def load_algolia_opts(session: requests.Session) -> dict:
    response = session.get(YC_COMPANIES_URL, timeout=30)
    response.raise_for_status()
    html = response.text

    marker_start = html.find(ALGOLIA_PREFIX)
    if marker_start == -1:
        raise RuntimeError("Could not find Algolia config marker in YC companies HTML.")
    json_start = marker_start + len(ALGOLIA_PREFIX)
    json_end = html.find("};", json_start)
    if json_end == -1:
        raise RuntimeError("Could not parse Algolia config JSON boundaries.")

    payload = html[json_start : json_end + 1]
    return json.loads(payload)


def fetch_page(
    session: requests.Session,
    *,
    app_id: str,
    api_key: str,
    index_name: str,
    page: int,
    hits_per_page: int,
    launched_before: int | None = None,
) -> dict:
    url = f"https://{app_id}-dsn.algolia.net/1/indexes/{index_name}/query"
    headers = {
        "X-Algolia-Application-Id": app_id,
        "X-Algolia-API-Key": api_key,
        "Content-Type": "application/json",
    }
    params = f"query=&hitsPerPage={hits_per_page}&page={page}"
    if launched_before is not None:
        params += f"&numericFilters=launched_at<{launched_before}"
    response = session.post(url, headers=headers, json={"params": params}, timeout=30)
    response.raise_for_status()
    return response.json()


def launched_at_to_iso(launched_at: int | None) -> str | None:
    if not launched_at:
        return None
    try:
        return dt.datetime.fromtimestamp(int(launched_at), tz=dt.timezone.utc).isoformat()
    except Exception:
        return None


def normalize_hit(hit: dict) -> dict:
    description = (hit.get("one_liner") or "").strip()
    if not description:
        description = (hit.get("long_description") or "").strip()

    launched_at_raw = hit.get("launched_at")
    launched_at_iso = launched_at_to_iso(launched_at_raw if isinstance(launched_at_raw, int | float) else None)

    return {
        "name": hit.get("name") or "",
        "description": description,
        "slug": hit.get("slug") or "",
        "website": hit.get("website") or "",
        "batch": hit.get("batch") or "",
        "launched_at": launched_at_raw,
        "launched_at_iso": launched_at_iso,
        "raw": hit,
    }


def write_markdown(output_path: Path, records: list[dict], *, index_name: str) -> None:
    generated_at = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    lines: list[str] = [
        "# YC Companies Raw Export",
        "",
        f"- Source: {YC_COMPANIES_URL}",
        f"- Index: {index_name}",
        f"- Generated At (UTC): {generated_at}",
        f"- Total Companies: {len(records)}",
        "",
    ]

    for i, record in enumerate(records, start=1):
        lines.append(f"## {i}. {record['name'] or 'Unknown Name'}")
        lines.append("")
        lines.append(f"- Description: {record['description'] or 'N/A'}")
        lines.append(f"- Launch Timestamp: {record['launched_at'] if record['launched_at'] is not None else 'N/A'}")
        lines.append(f"- Launch ISO: {record['launched_at_iso'] or 'N/A'}")
        lines.append(f"- Batch: {record['batch'] or 'N/A'}")
        lines.append(f"- Slug: {record['slug'] or 'N/A'}")
        lines.append(f"- Website: {record['website'] or 'N/A'}")
        lines.append("- Raw JSON:")
        lines.append("```json")
        lines.append(json.dumps(record["raw"], ensure_ascii=True))
        lines.append("```")
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
        else backend_root / "raw_documents" / f"yc_companies_launch_date_{timestamp}.md"
    )

    with requests.Session() as session:
        algolia_opts = load_algolia_opts(session)
        app_id = algolia_opts["app"]
        api_key = algolia_opts["key"]

        records: list[dict] = []
        launched_before: int | None = None
        windows_processed = 0
        max_windows = args.max_pages if args.max_pages is not None else None

        while True:
            first_page = fetch_page(
                session,
                app_id=app_id,
                api_key=api_key,
                index_name=args.index,
                page=0,
                hits_per_page=args.hits_per_page,
                launched_before=launched_before,
            )
            hits = first_page.get("hits", [])
            if not hits:
                break

            nb_pages = int(first_page["nbPages"])
            window_records = [normalize_hit(hit) for hit in hits]
            for page in range(1, nb_pages):
                payload = fetch_page(
                    session,
                    app_id=app_id,
                    api_key=api_key,
                    index_name=args.index,
                    page=page,
                    hits_per_page=args.hits_per_page,
                    launched_before=launched_before,
                )
                window_records.extend(normalize_hit(hit) for hit in payload.get("hits", []))
                if args.sleep_seconds > 0:
                    time.sleep(args.sleep_seconds)

            records.extend(window_records)
            windows_processed += 1

            launch_values = [r["launched_at"] for r in window_records if isinstance(r["launched_at"], (int, float))]
            if not launch_values:
                break
            launched_before = int(min(launch_values)) - 1

            if max_windows is not None and windows_processed >= max_windows:
                break
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    if args.sort == "asc":
        records.sort(
            key=lambda item: (item["launched_at"] is None, item["launched_at"] if item["launched_at"] is not None else 0)
        )
    else:
        records.sort(
            key=lambda item: (
                item["launched_at"] is not None,
                item["launched_at"] if item["launched_at"] is not None else -1,
            ),
            reverse=True,
        )

    write_markdown(output_path, records, index_name=args.index)
    print(f"[done] wrote {len(records)} YC company records to {output_path}")


if __name__ == "__main__":
    main()
