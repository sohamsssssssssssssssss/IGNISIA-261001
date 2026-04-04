from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List

from llama_index.core import Document


def stringify_payload(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, default=str)
    except TypeError:
        return str(payload)


def split_text(text: str, *, chunk_size: int = 1200, overlap: int = 120) -> List[str]:
    normalized = " ".join((text or "").split())
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: List[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunks.append(normalized[start:end])
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_documents(texts: Iterable[str], metadata: dict[str, Any]) -> List[Document]:
    documents: List[Document] = []
    for index, text in enumerate(texts):
        if not text.strip():
            continue
        doc_meta = dict(metadata)
        doc_meta["chunk_index"] = index
        documents.append(Document(text=text, metadata=doc_meta))
    return documents


def read_text_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
