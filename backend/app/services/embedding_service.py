"""
Lightweight embedding/index facade used by narratives, Apriori rule retrieval,
and score-payload enrichment.

The current implementation keeps a simple in-memory store so app startup and CI
do not depend on a heavy vector database being available.
"""

from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import Any, Dict, List


def _tokenize(text: str) -> set[str]:
    return {token for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if token}


class EmbeddingService:
    def __init__(self) -> None:
        self._collections: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)

    def bootstrap_static_documents(self) -> Dict[str, Any]:
        if self._collections["guidelines"]:
            return {"status": "ok", "seeded": 0}

        self.embed_document(
            "guideline:rbi-fair-practices",
            "RBI fair practices code requires transparency, adverse-action clarity, and defensible underwriting decisions.",
            {
                "collection": "guidelines",
                "doc_type": "rbi_guideline",
                "source": "RBI Fair Practices Code",
                "section": "Fair Practices",
            },
        )
        self.embed_document(
            "guideline:industry-manufacturing",
            "Manufacturing borrowers benefit from stable GST compliance, shipment momentum, and diversified counterparties.",
            {
                "collection": "guidelines",
                "doc_type": "industry_profile",
                "industry_label": "Manufacturing",
                "section": "Industry Profile",
            },
        )
        return {"status": "ok", "seeded": 2}

    def embed_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> None:
        collection = str(metadata.get("collection") or "documents")
        self._collections[collection][doc_id] = {
            "id": doc_id,
            "text": text,
            "metadata": dict(metadata),
            "tokens": _tokenize(text),
        }

    def embed_rule(self, rule_id: str, text: str, metadata: Dict[str, Any]) -> None:
        metadata = dict(metadata)
        metadata.setdefault("collection", "rules")
        metadata.setdefault("doc_type", metadata.get("rule_type") or "apriori_rule")
        self.embed_document(rule_id, text, metadata)

    def embed_score_payload(self, gstin: str, payload: Dict[str, Any]) -> None:
        summary = "\n".join(
            [
                f"GSTIN: {gstin}",
                f"Company: {payload.get('company_name')}",
                f"Credit Score: {payload.get('credit_score')}",
                f"Risk Band: {payload.get('risk_band', {}).get('band') if isinstance(payload.get('risk_band'), dict) else payload.get('risk_band')}",
                f"Fraud Risk: {payload.get('fraud_detection', {}).get('circular_risk')}",
                "Top Reasons:",
                *[
                    f"- {reason.get('feature') or reason.get('feature_key')}: {reason.get('reason')}"
                    for reason in payload.get("top_reasons", [])
                ],
            ]
        )
        self.embed_document(
            f"score:{gstin}:{payload.get('model_inference_at', 'latest')}",
            summary,
            {
                "collection": "score_history",
                "doc_type": "score_payload",
                "gstin": gstin,
                "company_name": payload.get("company_name"),
                "credit_score": payload.get("credit_score"),
                "risk_band": payload.get("risk_band", {}).get("band") if isinstance(payload.get("risk_band"), dict) else payload.get("risk_band"),
            },
        )

    def query_similar(self, collection: str, query: str, top_k: int = 5) -> Dict[str, Any]:
        query_tokens = _tokenize(query)
        rows = []
        for row in self._collections.get(collection, {}).values():
            overlap = len(query_tokens & row["tokens"])
            score = overlap / max(len(query_tokens) or 1, 1)
            rows.append((score, row))
        rows.sort(key=lambda item: item[0], reverse=True)
        selected = [row for score, row in rows[:top_k] if score > 0]
        return {
            "ids": [[row["id"] for row in selected]],
            "documents": [[row["text"] for row in selected]],
            "metadatas": [[row["metadata"] for row in selected]],
            "distances": [[1.0 - (len(query_tokens & row["tokens"]) / max(len(query_tokens) or 1, 1)) for row in selected]],
        }

    def get_collection_rows(self, collection: str) -> List[Dict[str, Any]]:
        return [
            {"id": row["id"], "text": row["text"], "metadata": row["metadata"]}
            for row in self._collections.get(collection, {}).values()
        ]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
