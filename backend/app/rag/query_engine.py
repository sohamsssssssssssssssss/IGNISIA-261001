"""
Trust-Weighted Query Engine — Synthesis layer.
Retrieves from all 3 collections, applies trust weighting, re-ranks,
and generates grounded answers via Ollama when available.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

try:
    import ollama
except ImportError:  # pragma: no cover - optional dependency
    ollama = None

from .indexer import DocumentIndexer


SYSTEM_PROMPT = """You are a senior Indian credit analyst preparing a Credit Appraisal Memo (CAM).
Answer based ONLY on the provided source excerpts.
Always cite which source your answer draws from using [SOURCE: name] format.
Never hallucinate numbers. If a number is not in the sources, say 'Not available in provided documents.'
Flag any inconsistencies between sources explicitly with the label [CONTRADICTION DETECTED]."""


@dataclass
class RAGResponse:
    answer: str
    sources_used: List[dict]
    confidence: str
    provenance_trail: str


class TrustWeightedQueryEngine:
    def __init__(
        self,
        borrower_indexer: DocumentIndexer,
        govt_indexer: DocumentIndexer,
        external_indexer: DocumentIndexer
    ):
        self.indexers = {
            "borrower": (borrower_indexer, 1.0),
            "govt":     (govt_indexer, 0.9),
            "external": (external_indexer, 0.6),
        }

    def _extractive_fallback(self, query_text: str, top_results: List[dict]) -> str:
        if not top_results:
            return (
                f"No grounded evidence was retrieved for query: {query_text}. "
                "Not available in provided documents."
            )

        lines = []
        for result in top_results[:3]:
            metadata = result.get("metadata", {})
            source = metadata.get("source") or metadata.get("source_url") or result.get("collection", "unknown")
            excerpt = " ".join(str(result.get("text", "")).split())
            excerpt = excerpt[:260].rstrip()
            lines.append(f"[SOURCE: {source}] {excerpt}")

        return "\n".join(lines)

    def query(self, query_text: str, top_k: int = 3) -> RAGResponse:
        all_results = []

        for source_name, (indexer, default_trust) in self.indexers.items():
            nodes = indexer.query(query_text, top_k=top_k)
            for node in nodes:
                trust = float(node["metadata"].get("trust_level", default_trust))
                node["weighted_score"] = (node.get("score") or 0.5) * trust
                node["collection"] = source_name
                all_results.append(node)

        all_results.sort(key=lambda x: x["weighted_score"], reverse=True)
        top_results = all_results[:5]

        context_blocks = []
        for r in top_results:
            meta = r["metadata"]
            src = meta.get("source", meta.get("source_url", r["collection"]))
            trust = r["metadata"].get("trust_level", "?")
            context_blocks.append(
                f"[SOURCE: {src} | Trust: {trust} | Score: {r['weighted_score']:.3f}]\n{r['text']}"
            )

        context = "\n\n---\n\n".join(context_blocks)
        user_message = f"QUERY: {query_text}\n\nSOURCES:\n{context}"

        avg_trust = sum(r["metadata"].get("trust_level", 0.7) for r in top_results) / max(len(top_results), 1)
        confidence = "HIGH" if avg_trust > 0.85 else "MEDIUM" if avg_trust > 0.65 else "LOW"

        provenance = " → ".join([
            f"{r['metadata'].get('source', r['collection'])} (trust={r['metadata'].get('trust_level','?')})"
            for r in top_results
        ])

        answer = self._extractive_fallback(query_text, top_results)
        if ollama is not None and top_results:
            try:
                response = ollama.chat(
                    model="llama3.2",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message}
                    ]
                )
                candidate = response["message"]["content"].strip()
                if candidate:
                    answer = candidate
            except Exception:
                pass

        return RAGResponse(
            answer=answer,
            sources_used=top_results,
            confidence=confidence,
            provenance_trail=provenance
        )
