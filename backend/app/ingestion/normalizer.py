from __future__ import annotations

import re
from dataclasses import dataclass

from app.ingestion.extractors import ExtractedDocument


@dataclass
class NormalizedDocument:
    title: str
    sections: list[tuple[str, str]]
    normalized_text: str


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _sections_from_markdown(text: str, fallback_title: str) -> tuple[str, list[tuple[str, str]]]:
    title = fallback_title
    sections: list[tuple[str, str]] = []
    heading = "Overview"
    buffer: list[str] = []

    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip() or title
            continue
        if line.startswith("## "):
            joined = "\n".join(buffer).strip()
            if joined:
                sections.append((heading, joined))
            heading = line[3:].strip() or "Overview"
            buffer = []
            continue
        buffer.append(line)

    joined = "\n".join(buffer).strip()
    if joined:
        sections.append((heading, joined))
    if not sections:
        sections = [("Overview", text)]
    return title, sections


def _sections_from_plain_text(text: str) -> list[tuple[str, str]]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return []

    sections: list[tuple[str, str]] = []
    current: list[str] = []
    char_budget = 3500
    index = 1
    total = 0
    for paragraph in paragraphs:
        if total + len(paragraph) > char_budget and current:
            sections.append((f"Section {index}", "\n\n".join(current)))
            index += 1
            current = []
            total = 0
        current.append(paragraph)
        total += len(paragraph)
    if current:
        sections.append((f"Section {index}", "\n\n".join(current)))
    return sections


def normalize_document(doc: ExtractedDocument) -> NormalizedDocument:
    cleaned = _clean_text(doc.text)
    if not cleaned:
        return NormalizedDocument(title=doc.title, sections=[], normalized_text="")

    if doc.file_type == "md":
        title, sections = _sections_from_markdown(cleaned, doc.title)
    else:
        title = doc.title
        sections = _sections_from_plain_text(cleaned)
        if not sections:
            sections = [("Overview", cleaned)]

    normalized_parts = [f"# {title}"]
    for section_name, content in sections:
        normalized_parts.append(f"\n## {section_name}\n{content}")
    normalized_text = "\n".join(normalized_parts).strip() + "\n"

    return NormalizedDocument(title=title, sections=sections, normalized_text=normalized_text)
