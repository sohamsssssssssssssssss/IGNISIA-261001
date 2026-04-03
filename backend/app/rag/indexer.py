"""
DocumentIndexer — LlamaIndex + HuggingFace embeddings over ChromaDB.
Supports semantic queries and structured metadata filtering.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Document, Settings
from typing import Any, Dict, List, Optional


Settings.embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
Settings.llm = None  # We use Ollama separately for generation


class DocumentIndexer:
    def __init__(self, collection):
        self.collection = collection
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        self.index = VectorStoreIndex([], storage_context=storage_context)

    def _normalize_document(
        self,
        doc: Document,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        document_id: str | None = None,
        source_kind: str | None = None,
        source_label: str | None = None,
        doc_type: str | None = None,
        source_path: str | None = None,
        ingestion_version: str | None = None,
    ) -> Document:
        text = " ".join((doc.text or "").split())
        content_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
        normalized_doc_id = document_id or source_label or source_path or "unknown_document"
        normalized_chunk_id = f"{session_id or 'shared'}:{normalized_doc_id}:{content_hash[:16]}"
        metadata: Dict[str, Any] = dict(doc.metadata or {})

        metadata.setdefault("chunk_id", normalized_chunk_id)
        metadata.setdefault("content_hash", content_hash)
        metadata.setdefault("document_id", normalized_doc_id)
        metadata.setdefault("source_label", source_label or metadata.get("source_title") or normalized_doc_id)
        metadata.setdefault("source_kind", source_kind or "uploaded_document")
        metadata.setdefault("session_id", session_id or "shared")
        metadata.setdefault("pipeline_run_id", run_id or metadata.get("pipeline_run_id"))
        metadata.setdefault("ingestion_version", ingestion_version or run_id or "v1")
        metadata.setdefault("ingested_at", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        metadata.setdefault("doc_type", doc_type or metadata.get("doc_type") or "unknown")
        if source_path:
            metadata.setdefault("source_path", source_path)

        doc.metadata = metadata
        if hasattr(doc, "id_"):
            setattr(doc, "id_", normalized_chunk_id)
        if hasattr(doc, "doc_id"):
            setattr(doc, "doc_id", normalized_chunk_id)
        return doc

    def add_documents(
        self,
        documents: List[Document],
        *,
        session_id: str | None = None,
        run_id: str | None = None,
        document_id: str | None = None,
        source_kind: str | None = None,
        source_label: str | None = None,
        doc_type: str | None = None,
        source_path: str | None = None,
        ingestion_version: str | None = None,
    ):
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
            dedupe_key = (
                doc.metadata.get("session_id"),
                doc.metadata.get("document_id"),
                doc.metadata.get("content_hash"),
            )
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            self.index.insert(doc)
            inserted += 1
        return inserted

    def query(
        self,
        query_text: str,
        doc_type_filter: Optional[str] = None,
        top_k: int = 5
    ) -> List[dict]:
        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query_text)

        results = []
        for node in nodes:
            meta = node.metadata
            if doc_type_filter and meta.get("doc_type") != doc_type_filter:
                continue
            results.append({
                "text": node.text,
                "metadata": meta,
                "score": node.score,
                "trust_level": float(meta.get("trust_level", 1.0))
            })

        return results

    def query_by_metadata(self, filters: dict, top_k: int = 10) -> List[dict]:
        """Query by exact metadata match — e.g. find all nach_bounces > 0"""
        from llama_index.core.vector_stores import MetadataFilter, MetadataFilters
        llama_filters = MetadataFilters(filters=[
            MetadataFilter(key=k, value=v) for k, v in filters.items()
        ])
        retriever = self.index.as_retriever(
            similarity_top_k=top_k,
            filters=llama_filters
        )
        nodes = retriever.retrieve("")
        return [{"text": n.text, "metadata": n.metadata, "score": n.score} for n in nodes]
