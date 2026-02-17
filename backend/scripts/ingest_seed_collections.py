from __future__ import annotations

import argparse
import os
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
SEED_ROOT = Path(__file__).resolve().parents[1] / "seed_documents"


@dataclass
class SectionChunk:
    source: str
    title: str
    section: str
    content: str


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
        embeddings = [item["embedding"] for item in data]
        return embeddings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="search_document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="search_query")[0]


class CohereEmbeddingProvider:
    def __init__(self, api_key: str, model_name: str) -> None:
        import cohere  # local import so cohere is optional when using OpenRouter

        self.client = cohere.Client(api_key=api_key)
        self.model_name = model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embed(
            model=self.model_name,
            input_type="search_document",
            texts=texts,
        )
        embeddings = response.embeddings
        if hasattr(embeddings, "float"):
            embeddings = embeddings.float
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        response = self.client.embed(
            model=self.model_name,
            input_type="search_query",
            texts=[text],
        )
        embeddings = response.embeddings
        if hasattr(embeddings, "float"):
            embeddings = embeddings.float
        return embeddings[0]


def parse_markdown_sections(path: Path) -> list[SectionChunk]:
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
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line[3:].strip() or "Overview"
            current_lines = []
            continue
        current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n### ", "\n\n## ", "\n\n", "\n", ". ", " "],
        chunk_size=900,
        chunk_overlap=120,
        length_function=len,
    )

    chunks: list[SectionChunk] = []
    for section, section_lines in sections:
        section_text = "\n".join(section_lines).strip()
        if not section_text:
            continue
        for chunk in splitter.split_text(section_text):
            clean_chunk = chunk.strip()
            if not clean_chunk:
                continue
            chunks.append(
                SectionChunk(
                    source=str(path.relative_to(SEED_ROOT)),
                    title=title,
                    section=section,
                    content=clean_chunk,
                )
            )
    return chunks


def embed_chunks(provider: EmbeddingProvider, chunks: list[SectionChunk]) -> list[list[float]]:
    if not chunks:
        return []
    embeddings = provider.embed_documents([chunk.content for chunk in chunks])
    if not embeddings:
        raise RuntimeError("Embedding provider returned empty embeddings")
    if len(embeddings[0]) != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"Unexpected embedding dimension: {len(embeddings[0])}. "
            f"Expected {EMBEDDING_DIMENSION}. Change model or migration dimension."
        )
    return embeddings


def ingest_collection(provider: EmbeddingProvider, collection_name: str, append: bool) -> int:
    model = COLLECTION_MODEL_MAP[collection_name]
    docs_dir = SEED_ROOT / collection_name
    markdown_files = sorted(docs_dir.glob("*.md"))
    if not markdown_files:
        print(f"[skip] {collection_name}: no markdown files under {docs_dir}")
        return 0

    chunks: list[SectionChunk] = []
    for file_path in markdown_files:
        chunks.extend(parse_markdown_sections(file_path))
    embeddings = embed_chunks(provider, chunks)

    with SessionLocal() as session:
        if not append:
            session.execute(delete(model))
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            session.add(
                model(
                    content=chunk.content,
                    embedding=embedding,
                    doc_metadata={
                        "source": chunk.source,
                        "title": chunk.title,
                        "section": chunk.section,
                    },
                )
            )
        session.commit()

    print(f"[ok] {collection_name}: ingested {len(chunks)} chunks from {len(markdown_files)} docs")
    return len(chunks)


def run_vector_query(collection_name: str, query: str, provider: EmbeddingProvider) -> None:
    model = COLLECTION_MODEL_MAP[collection_name]
    query_embedding = provider.embed_query(query)

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
    parser.add_argument("--append", action="store_true", help="Append instead of replacing existing rows.")
    parser.add_argument("--verify", action="store_true", help="Run vector and keyword test queries after ingestion.")
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
    provider = build_embedding_provider(args)
    print(f"[config] provider={args.embedding_provider} model={provider.model_name}")
    total_chunks = 0
    for collection_name in COLLECTION_MODEL_MAP:
        total_chunks += ingest_collection(provider, collection_name, append=args.append)
    print(f"\n[done] total chunks ingested: {total_chunks}")

    if args.verify:
        run_vector_query("founder_principles_docs", "What habits make startup founders effective?", provider)
        run_keyword_query("technical_constraints_docs", "latency budget")


if __name__ == "__main__":
    main()
