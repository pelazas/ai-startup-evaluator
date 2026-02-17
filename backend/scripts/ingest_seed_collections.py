from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from langchain_text_splitters import RecursiveCharacterTextSplitter
import requests
from sqlalchemy import delete, func, select

from app.config import settings
from app.database import SessionLocal
from app.models.vector_collection import (
    AIMarketDataDoc,
    FounderPrinciplesDoc,
    PersonalProfileDoc,
    StartupExamplesDoc,
    TechnicalConstraintsDoc,
)

EMBEDDING_DIMENSION = 1024
BACKEND_ROOT = Path(__file__).resolve().parents[1]
SEED_ROOT = BACKEND_ROOT / "seed_documents"
CHECKPOINT_ROOT = BACKEND_ROOT / ".ingestion_state" / "checkpoints"
MAX_RETRIES = 5


@dataclass
class SectionChunk:
    source: str
    title: str
    section: str
    content: str
    doc_hash: str
    chunk_hash: str
    profile: str


@dataclass
class ChunkingPolicy:
    name: str
    chunk_size: int
    chunk_overlap: int
    embedding_batch_size: int


COLLECTION_MODEL_MAP = {
    "founder_principles_docs": FounderPrinciplesDoc,
    "ai_market_data_docs": AIMarketDataDoc,
    "startup_examples_docs": StartupExamplesDoc,
    "technical_constraints_docs": TechnicalConstraintsDoc,
    "personal_profile_docs": PersonalProfileDoc,
}


class EmbeddingProvider(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OpenRouterEmbeddingProvider:
    def __init__(self, api_key: str, model_name: str) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://openrouter.ai/api/v1/embeddings"

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "input": texts,
                "input_type": input_type,
                "encoding_format": "float",
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        return [item["embedding"] for item in data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="search_document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="search_query")[0]


class CohereEmbeddingProvider:
    def __init__(self, api_key: str, model_name: str) -> None:
        import cohere  # local import keeps cohere optional

        self.client = cohere.Client(api_key=api_key)
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embed(model=self.model_name, input_type="search_document", texts=texts)
        embeddings = response.embeddings
        if hasattr(embeddings, "float"):
            embeddings = embeddings.float
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        response = self.client.embed(model=self.model_name, input_type="search_query", texts=[text])
        embeddings = response.embeddings
        if hasattr(embeddings, "float"):
            embeddings = embeddings.float
        return embeddings[0]


def _detect_policy(char_count: int) -> ChunkingPolicy:
    if char_count <= 3000:
        return ChunkingPolicy(name="small", chunk_size=900, chunk_overlap=120, embedding_batch_size=64)
    if char_count <= 15000:
        return ChunkingPolicy(name="medium", chunk_size=820, chunk_overlap=110, embedding_batch_size=48)
    if char_count <= 60000:
        return ChunkingPolicy(name="large", chunk_size=700, chunk_overlap=95, embedding_batch_size=32)
    return ChunkingPolicy(name="huge", chunk_size=560, chunk_overlap=80, embedding_batch_size=16)


def _parse_markdown_sections(path: Path, seed_root: Path) -> tuple[str, str, list[tuple[str, str]]]:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    title = path.stem.replace("_", " ").title()
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Overview"
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip() or title
            continue
        if line.startswith("## "):
            joined = "\n".join(current_lines).strip()
            if joined:
                sections.append((current_heading, current_lines))
            current_heading = line[3:].strip() or "Overview"
            current_lines = []
            continue
        current_lines.append(line)

    joined = "\n".join(current_lines).strip()
    if joined:
        sections.append((current_heading, current_lines))

    merged = "\n".join(["\n".join(lines).strip() for _, lines in sections]).strip()
    source = str(path.relative_to(seed_root))
    compact_sections = [(name, "\n".join(content_lines).strip()) for name, content_lines in sections if "\n".join(content_lines).strip()]
    return source, title, compact_sections if compact_sections else [("Overview", raw.strip())]


def _stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_sidecar_metadata(path: Path) -> dict:
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return {}
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def parse_seed_chunks(path: Path, seed_root: Path) -> tuple[list[SectionChunk], dict]:
    source, title, sections = _parse_markdown_sections(path, seed_root)
    file_text = path.read_text(encoding="utf-8")
    policy = _detect_policy(len(file_text))
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n### ", "\n\n## ", "\n\n", "\n", ". ", " "],
        chunk_size=policy.chunk_size,
        chunk_overlap=policy.chunk_overlap,
        length_function=len,
    )

    doc_hash = _stable_hash(file_text)
    chunks: list[SectionChunk] = []
    for section_name, section_text in sections:
        for piece in splitter.split_text(section_text):
            content = piece.strip()
            if not content:
                continue
            chunk_hash = _stable_hash(f"{source}|{section_name}|{content}")
            chunks.append(
                SectionChunk(
                    source=source,
                    title=title,
                    section=section_name,
                    content=content,
                    doc_hash=doc_hash,
                    chunk_hash=chunk_hash,
                    profile=policy.name,
                )
            )
    return chunks, {"policy": policy, "sidecar": _load_sidecar_metadata(path)}


def _with_retry(label: str, fn):
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            backoff = min(2**attempt, 20)
            print(f"[retry] {label} attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(backoff)
    raise RuntimeError(f"{label} failed after {MAX_RETRIES} attempts: {last_exc}")


def embed_chunks_batched(provider: EmbeddingProvider, chunks: list[SectionChunk], batch_size: int) -> list[list[float]]:
    if not chunks:
        return []
    embeddings: list[list[float]] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        batch_embeddings = _with_retry(
            f"embed batch {start // batch_size + 1}",
            lambda: provider.embed_documents([chunk.content for chunk in batch]),
        )
        if not batch_embeddings:
            raise RuntimeError("Embedding provider returned empty batch")
        if len(batch_embeddings[0]) != EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Unexpected embedding dimension: {len(batch_embeddings[0])}. Expected {EMBEDDING_DIMENSION}."
            )
        embeddings.extend(batch_embeddings)
    return embeddings


def _checkpoint_path(collection_name: str) -> Path:
    CHECKPOINT_ROOT.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_ROOT / f"{collection_name}.json"


def load_checkpoint(collection_name: str) -> dict:
    path = _checkpoint_path(collection_name)
    if not path.exists():
        return {"next_index": 0, "fingerprint": ""}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"next_index": 0, "fingerprint": ""}


def save_checkpoint(collection_name: str, next_index: int, fingerprint: str) -> None:
    path = _checkpoint_path(collection_name)
    path.write_text(json.dumps({"next_index": next_index, "fingerprint": fingerprint}, indent=2) + "\n", encoding="utf-8")


def _collection_fingerprint(chunks: list[SectionChunk]) -> str:
    joined = "|".join(chunk.chunk_hash for chunk in chunks)
    return _stable_hash(joined)


def _existing_chunk_hashes(session, model) -> set[str]:
    rows = session.execute(select(model.doc_metadata["chunk_hash"].astext).where(model.doc_metadata["chunk_hash"].astext.is_not(None))).all()
    return {value for (value,) in rows if value}


def ingest_collection(provider: EmbeddingProvider | None, collection_name: str, args: argparse.Namespace) -> int:
    model = COLLECTION_MODEL_MAP[collection_name]
    docs_dir = Path(args.seed_root) / collection_name
    markdown_files = sorted(docs_dir.glob("*.md"))
    if not markdown_files:
        print(f"[skip] {collection_name}: no markdown files under {docs_dir}")
        return 0

    chunks: list[SectionChunk] = []
    selected_batch_size = 32
    sidecars: dict[str, dict] = {}
    profiles: dict[str, int] = {}
    for file_path in markdown_files:
        parsed_chunks, info = parse_seed_chunks(file_path, Path(args.seed_root))
        sidecars[str(file_path.relative_to(Path(args.seed_root)))] = info["sidecar"]
        policy: ChunkingPolicy = info["policy"]
        selected_batch_size = min(selected_batch_size, policy.embedding_batch_size)
        profiles[policy.name] = profiles.get(policy.name, 0) + 1
        chunks.extend(parsed_chunks)

    if not chunks:
        print(f"[skip] {collection_name}: files found but no valid chunks")
        return 0

    fingerprint = _collection_fingerprint(chunks)
    checkpoint = load_checkpoint(collection_name)
    start_index = checkpoint.get("next_index", 0) if checkpoint.get("fingerprint") == fingerprint else 0

    if not args.dry_run:
        with SessionLocal() as session:
            if not args.append and not args.resume and start_index == 0:
                session.execute(delete(model))
                session.commit()

    chunks_to_process = chunks[start_index:]
    if not chunks_to_process:
        print(f"[ok] {collection_name}: nothing to process (checkpoint already complete)")
        return 0

    if args.dry_run or args.force_reindex:
        existing_hashes = set()
    else:
        with SessionLocal() as session:
            existing_hashes = _existing_chunk_hashes(session, model)

    filtered_chunks = [chunk for chunk in chunks_to_process if chunk.chunk_hash not in existing_hashes]
    if not filtered_chunks:
        print(f"[ok] {collection_name}: all chunks already ingested")
        save_checkpoint(collection_name, len(chunks), fingerprint)
        return 0

    if args.dry_run:
        print(
            f"[dry-run] {collection_name}: files={len(markdown_files)} total_chunks={len(chunks)} "
            f"new_chunks={len(filtered_chunks)} profiles={profiles} batch={selected_batch_size}"
        )
        return len(filtered_chunks)

    if provider is None:
        raise RuntimeError("Embedding provider is required when not running --dry-run.")

    embeddings = embed_chunks_batched(provider, filtered_chunks, batch_size=selected_batch_size)

    inserted = 0
    with SessionLocal() as session:
        for chunk, embedding in zip(filtered_chunks, embeddings, strict=True):
            source_metadata = sidecars.get(chunk.source, {})
            session.add(
                model(
                    content=chunk.content,
                    embedding=embedding,
                    doc_metadata={
                        "source": chunk.source,
                        "title": chunk.title,
                        "section": chunk.section,
                        "doc_hash": chunk.doc_hash,
                        "chunk_hash": chunk.chunk_hash,
                        "chunk_profile": chunk.profile,
                        **source_metadata,
                    },
                )
            )
            inserted += 1
        session.commit()

    save_checkpoint(collection_name, len(chunks), fingerprint)
    print(
        f"[ok] {collection_name}: files={len(markdown_files)} total_chunks={len(chunks)} "
        f"new_chunks={len(filtered_chunks)} inserted={inserted} "
        f"profiles={profiles} batch={selected_batch_size}"
    )
    return len(filtered_chunks)


def run_vector_query(collection_name: str, query: str, provider: EmbeddingProvider) -> None:
    model = COLLECTION_MODEL_MAP[collection_name]
    query_embedding = _with_retry("embed query", lambda: provider.embed_query(query))
    with SessionLocal() as session:
        rows = session.execute(
            select(
                model.doc_metadata,
                model.content,
                model.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .order_by("distance")
            .limit(3)
        ).all()
    print(f"\n[vector test] {collection_name} -> '{query}'")
    for metadata, content, distance in rows:
        print(f"- distance={distance:.4f} source={metadata.get('source')} section={metadata.get('section')}")
        print(f"  snippet={content[:120].replace(chr(10), ' ')}...")


def run_keyword_query(collection_name: str, query: str) -> None:
    model = COLLECTION_MODEL_MAP[collection_name]
    with SessionLocal() as session:
        rows = session.execute(
            select(model.doc_metadata, model.content)
            .where(model.content_tsvector.op("@@")(func.plainto_tsquery("english", query)))
            .limit(3)
        ).all()
    print(f"\n[keyword test] {collection_name} -> '{query}'")
    for metadata, content in rows:
        print(f"- source={metadata.get('source')} section={metadata.get('section')}")
        print(f"  snippet={content[:120].replace(chr(10), ' ')}...")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest seed docs into vector collections.")
    parser.add_argument("--seed-root", default=str(SEED_ROOT), help="Seed document root.")
    parser.add_argument("--append", action="store_true", help="Append mode. Keep existing rows.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare chunks but do not write to DB.")
    parser.add_argument("--verify", action="store_true", help="Run vector and keyword test queries after ingestion.")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint.")
    parser.add_argument("--force-reindex", action="store_true", help="Ignore idempotency hash checks.")
    parser.add_argument(
        "--embedding-provider",
        choices=["openrouter", "cohere"],
        default="openrouter",
        help="Embedding provider. Default: openrouter.",
    )
    parser.add_argument("--embedding-model", default=None, help="Override embedding model ID.")
    return parser.parse_args()


def build_embedding_provider(args: argparse.Namespace) -> EmbeddingProvider:
    if args.embedding_provider == "openrouter":
        api_key = settings.open_router_api_key or os.getenv("OPEN_ROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPEN_ROUTER_API_KEY is required for OpenRouter embeddings.")
        model_name = args.embedding_model or os.getenv("OPENROUTER_EMBEDDING_MODEL") or "cohere/embed-english-v3.0"
        return OpenRouterEmbeddingProvider(api_key=api_key, model_name=model_name)

    api_key = settings.cohere_api_key or os.getenv("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is required for Cohere embeddings.")
    model_name = args.embedding_model or os.getenv("COHERE_EMBEDDING_MODEL") or "embed-english-v3.0"
    return CohereEmbeddingProvider(api_key=api_key, model_name=model_name)


def main() -> None:
    args = parse_args()
    provider: EmbeddingProvider | None = None
    if args.dry_run:
        print("[config] dry-run mode enabled; embeddings and DB writes are skipped")
    else:
        provider = build_embedding_provider(args)
        print(f"[config] provider={args.embedding_provider} model={provider.model_name}")
    total_new_chunks = 0
    for collection_name in COLLECTION_MODEL_MAP:
        total_new_chunks += ingest_collection(provider, collection_name, args)
    print(f"\n[done] new chunks processed: {total_new_chunks}")

    if args.verify and not args.dry_run and provider is not None:
        run_vector_query("founder_principles_docs", "What habits make startup founders effective?", provider)
        run_keyword_query("technical_constraints_docs", "latency budget")


if __name__ == "__main__":
    main()
