from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ingestion import (
    build_metadata,
    classify_document,
    compute_content_hash,
    extract_document,
    make_document_id,
    normalize_document,
)
from app.ingestion.extractors import SUPPORTED_EXTENSIONS

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = BACKEND_ROOT / "raw_documents"
PROCESSED_ROOT = BACKEND_ROOT / "processed_documents"
SEED_ROOT = BACKEND_ROOT / "seed_documents"
REVIEW_ROOT = PROCESSED_ROOT / "review_queue"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess raw documents into classified seed documents.")
    parser.add_argument("--raw-root", default=str(RAW_ROOT), help="Root folder containing raw docs.")
    parser.add_argument("--seed-root", default=str(SEED_ROOT), help="Output seed folder root.")
    parser.add_argument("--processed-root", default=str(PROCESSED_ROOT), help="Output processed folder root.")
    parser.add_argument("--review-threshold", type=float, default=0.65, help="Confidence threshold for auto-routing.")
    parser.add_argument("--llm-threshold", type=float, default=0.55, help="Only use LLM fallback below this confidence.")
    parser.add_argument("--rules-only", action="store_true", help="Disable OpenRouter classification fallback.")
    parser.add_argument("--dry-run", action="store_true", help="Run classification without writing files.")
    return parser.parse_args()


def _iter_supported_files(raw_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in raw_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return sorted(files)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    raw_root = Path(args.raw_root).resolve()
    seed_root = Path(args.seed_root).resolve()
    processed_root = Path(args.processed_root).resolve()
    review_root = processed_root / "review_queue"

    files = _iter_supported_files(raw_root)
    if not files:
        print(f"[done] no supported files found in {raw_root}")
        return

    routed = 0
    review = 0
    failed = 0
    for path in files:
        try:
            extracted = extract_document(path, raw_root=raw_root)
            normalized = normalize_document(extracted)
            if not normalized.normalized_text.strip():
                print(f"[skip] {extracted.source}: empty after normalization")
                continue

            classification = classify_document(
                normalized,
                llm_threshold=args.llm_threshold,
                allow_llm=not args.rules_only,
            )
            content_hash = compute_content_hash(normalized.normalized_text)
            doc_id = make_document_id(extracted.source, content_hash)
            metadata = build_metadata(
                source=extracted.source,
                title=normalized.title,
                file_type=extracted.file_type,
                collection=classification.collection,
                confidence=classification.confidence,
                content_hash=content_hash,
                section_count=len(normalized.sections),
                classification_reason=f"{classification.method}: {classification.reason}",
            )

            if classification.collection is None or classification.confidence < args.review_threshold:
                review += 1
                queue_payload = {
                    "doc_id": doc_id,
                    "metadata": metadata,
                    "suggested_collection": classification.collection,
                    "confidence": classification.confidence,
                    "preview": normalized.normalized_text[:4000],
                }
                if not args.dry_run:
                    _write_json(review_root / f"{doc_id}.json", queue_payload)
                print(
                    f"[review] {extracted.source} -> {classification.collection} "
                    f"(confidence={classification.confidence:.2f})"
                )
                continue

            routed += 1
            collection = classification.collection
            processed_doc_dir = processed_root / collection / doc_id
            seed_doc_path = seed_root / collection / f"{doc_id}.md"
            seed_meta_path = seed_root / collection / f"{doc_id}.json"
            processed_meta = {
                "doc_id": doc_id,
                "metadata": metadata,
                "sections": [name for name, _ in normalized.sections],
            }

            if not args.dry_run:
                _write_text(processed_doc_dir / "content.md", normalized.normalized_text)
                _write_json(processed_doc_dir / "metadata.json", processed_meta)
                _write_text(seed_doc_path, normalized.normalized_text)
                _write_json(seed_meta_path, {"doc_id": doc_id, **metadata})

            print(f"[routed] {extracted.source} -> {collection} (confidence={classification.confidence:.2f})")

        except Exception as exc:
            failed += 1
            error_payload = {
                "source": str(path),
                "error": str(exc),
            }
            if not args.dry_run:
                _write_json(review_root / f"error_{path.stem}.json", error_payload)
            print(f"[error] {path}: {exc}")

    summary = {
        "total_files": len(files),
        "routed": routed,
        "review": review,
        "failed": failed,
    }
    if not args.dry_run:
        _write_json(processed_root / "last_preprocess_summary.json", summary)
    print(f"[done] {summary}")


if __name__ == "__main__":
    main()
