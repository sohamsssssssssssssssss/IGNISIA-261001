"""
DocumentIndexer with Chroma/LlamaIndex support and an in-memory fallback.

Python 3.14 currently breaks the installed Chroma runtime in this project, so
the fallback keeps the CAM pipeline operational for local/demo use.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
    from llama_index.vector_stores.chroma import ChromaVectorStore

    HAS_LLAMA_INDEX = True
except Exception:  # pragma: no cover - optional dependency/runtime compatibility varies by env
    Document = None
    Settings = None
    StorageContext = None
    VectorStoreIndex = None
    HuggingFaceEmbedding = None
    ChromaVectorStore = None
    HAS_LLAMA_INDEX = False


if HAS_LLAMA_INDEX and Settings is not None:
    Settings.embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    Settings.llm = None


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
        if token
    }


def _coerce_text(doc: Any) -> str:
    return str(getattr(doc, "text", "") or "")


def _coerce_metadata(doc: Any) -> Dict[str, Any]:
    metadata = getattr(doc, "metadata", None)
    return dict(metadata or {})


def _set_doc_identity(doc: Any, normalized_chunk_id: str) -> None:
    if hasattr(doc, "id_"):
        setattr(doc, "id_", normalized_chunk_id)
    if hasattr(doc, "doc_id"):
        setattr(doc, "doc_id", normalized_chunk_id)


@dataclass
class _MemoryRow:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens: set[str] = field(default_factory=set)


class DocumentIndexer:
    def __init__(self, collection):
        self.collection = collection
        self._memory_rows: List[_MemoryRow] = []
        self._backend = "memory"
        self.index = None

        if HAS_LLAMA_INDEX and collection is not None:
            try:
                vector_store = ChromaVectorStore(chroma_collection=collection)
                storage_context = StorageContext.from_defaults(vector_store=vector_store)
                self.index = VectorStoreIndex([], storage_context=storage_context)
                self._backend = "chroma"
            except Exception:
                self.index = None
                self._backend = "memory"

    def _normalize_document(
        self,
        doc: Any,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        document_id: str | None = None,
        source_kind: str | None = None,
        source_label: str | None = None,
        doc_type: str | None = None,
        source_path: str | None = None,
        ingestion_version: str | None = None,
    ) -> Any:
        text = " ".join(_coerce_text(doc).split())
        content_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
        normalized_doc_id = document_id or source_label or source_path or "unknown_document"
        normalized_chunk_id = f"{session_id or 'shared'}:{normalized_doc_id}:{content_hash[:16]}"
        metadata: Dict[str, Any] = _coerce_metadata(doc)

        metadata.setdefault("chunk_id", normalized_chunk_id)
        metadata.setdefault("content_hash", content_hash)
        metadata.setdefault("document_id", normalized_doc_id)
        metadata.setdefault(
            "source_label",
            source_label or metadata.get("source_title") or normalized_doc_id,
        )
        metadata.setdefault("source_kind", source_kind or "uploaded_document")
        metadata.setdefault("session_id", session_id or "shared")
        metadata.setdefault("pipeline_run_id", run_id or metadata.get("pipeline_run_id"))
        metadata.setdefault("ingestion_version", ingestion_version or run_id or "v1")
        metadata.setdefault(
            "ingested_at",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        metadata.setdefault("doc_type", doc_type or metadata.get("doc_type") or "unknown")
        if source_path:
            metadata.setdefault("source_path", source_path)

        if hasattr(doc, "metadata"):
            doc.metadata = metadata
            _set_doc_identity(doc, normalized_chunk_id)
            return doc

        return type(
            "FallbackDocument",
            (),
            {"text": text, "metadata": metadata, "id_": normalized_chunk_id, "doc_id": normalized_chunk_id},
        )()

    def add_documents(
        self,
        documents: List[Any],
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        document_id: str | None = None,
        source_kind: str | None = None,
        source_label: str | None = None,
        doc_type: str | None = None,
        source_path: str | None = None,
        ingestion_version: str | None = None,
    ) -> int:
        inserted = 0
        seen_keys = set()
        for raw_doc in documents:
            doc = self._normalize_document(
                raw_doc,
                session_id=session_id,
                run_id=run_id,
                document_id=document_id,
                source_kind=source_kind,
                source_label=source_label,
                doc_type=doc_type,
                source_path=source_path,
                ingestion_version=ingestion_version,
            )
            metadata = _coerce_metadata(doc)
            dedupe_key = (
                metadata.get("session_id"),
                metadata.get("document_id"),
                metadata.get("content_hash"),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            if self._backend == "chroma" and self.index is not None:
                self.index.insert(doc)
            else:
                text = _coerce_text(doc)
                self._memory_rows.append(
                    _MemoryRow(text=text, metadata=metadata, tokens=_tokenize(text))
                )
            inserted += 1
        return inserted

    def _query_memory(
        self,
        query_text: str,
        *,
        doc_type_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[dict]:
        query_tokens = _tokenize(query_text)
        rows = []
        for row in self._memory_rows:
            if doc_type_filter and row.metadata.get("doc_type") != doc_type_filter:
                continue
            overlap = len(query_tokens & row.tokens)
            score = overlap / max(len(query_tokens) or 1, 1) if query_tokens else 0.0
            rows.append(
                {
                    "text": row.text,
                    "metadata": row.metadata,
                    "score": score,
                    "trust_level": float(row.metadata.get("trust_level", 1.0)),
                }
            )
        rows.sort(key=lambda item: item["score"], reverse=True)
        return [row for row in rows[:top_k] if row["score"] > 0 or not query_tokens]

    def query(
        self,
        query_text: str,
        doc_type_filter: Optional[str] = None,
        top_k: int = 5,
    ) -> List[dict]:
        if self._backend != "chroma" or self.index is None:
            return self._query_memory(
                query_text,
                doc_type_filter=doc_type_filter,
                top_k=top_k,
            )

        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query_text)

        results = []
        for node in nodes:
            meta = node.metadata
            if doc_type_filter and meta.get("doc_type") != doc_type_filter:
                continue
            results.append(
                {
                    "text": node.text,
                    "metadata": meta,
                    "score": node.score,
                    "trust_level": float(meta.get("trust_level", 1.0)),
                }
            )
        return results

    def query_by_metadata(self, filters: dict, top_k: int = 10) -> List[dict]:
        if self._backend != "chroma" or self.index is None:
            matches = []
            for row in self._memory_rows:
                if all(row.metadata.get(key) == value for key, value in filters.items()):
                    matches.append({"text": row.text, "metadata": row.metadata, "score": 1.0})
            return matches[:top_k]

        from llama_index.core.vector_stores import MetadataFilter, MetadataFilters

        llama_filters = MetadataFilters(
            filters=[MetadataFilter(key=k, value=v) for k, v in filters.items()]
        )
        retriever = self.index.as_retriever(similarity_top_k=top_k, filters=llama_filters)
        nodes = retriever.retrieve("")
        return [{"text": n.text, "metadata": n.metadata, "score": n.score} for n in nodes]
