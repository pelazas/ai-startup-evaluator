from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


@dataclass
class ExtractedDocument:
    path: Path
    source: str
    title: str
    file_type: str
    text: str


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages).strip()


def extract_document(path: Path, raw_root: Path) -> ExtractedDocument:
    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file format: {extension}")

    if extension == ".pdf":
        text = _read_pdf(path)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")

    relative_source = str(path.relative_to(raw_root))
    title = path.stem.replace("_", " ").replace("-", " ").strip().title()

    return ExtractedDocument(
        path=path,
        source=relative_source,
        title=title,
        file_type=extension.lstrip("."),
        text=text.strip(),
    )
