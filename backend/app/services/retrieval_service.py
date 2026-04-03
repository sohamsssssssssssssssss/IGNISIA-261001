"""
Retrieval helpers for narratives and analyst chat.

This keeps retrieval deterministic and storage-backed so the app can operate
without external vector infra during tests and bootstrap.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List

from ..core.storage import get_storage
from .embedding_service import get_embedding_service


def _similarity_from_scores(a: float, b: float) -> float:
    return max(0.0, 1.0 - (abs(a - b) / 600.0))


class RetrievalService:
    def __init__(self, *, storage=None, embedding_service=None) -> None:
        self.storage = storage or get_storage()
        self.embedding_service = embedding_service or get_embedding_service()

    def seed_synthetic_history_if_empty(self, min_cases: int = 100) -> Dict[str, Any]:
        current = self.storage.count_loan_outcomes()
        if current >= min_cases:
            return {"status": "ok", "seeded": 0, "total_cases": current}
        return {"status": "ok", "seeded": 0, "total_cases": current}

    def get_similar_cases(self, gstin: str, score_payload: Dict[str, Any], k: int = 3) -> List[Dict[str, Any]]:
        outcomes = self.storage.get_loan_outcomes()
        target_score = float(score_payload.get("credit_score") or 0.0)
        cases: List[Dict[str, Any]] = []

        for outcome in outcomes:
            if outcome["gstin"] == gstin:
                continue
            assessment = self.storage.get_latest_assessment_details(outcome["gstin"])
            if assessment is None:
                continue
            similarity = _similarity_from_scores(target_score, float(assessment.get("credit_score") or 0.0))
            cases.append(
                {
                    "id": f"score:{outcome['gstin']}",
                    "collection": "score_history",
                    "gstin": outcome["gstin"],
                    "company_name": assessment.get("company_name"),
                    "credit_score": assessment.get("credit_score"),
                    "risk_band": assessment.get("risk_band"),
                    "similarity": round(similarity, 4),
                    "outcome": {"status": "repaid" if outcome.get("repaid") else "defaulted"},
                    "summary": (
                        f"{assessment.get('company_name') or outcome['gstin']} scored "
                        f"{assessment.get('credit_score')} and "
                        f"{'repaid' if outcome.get('repaid') else 'defaulted'}."
                    ),
                    "metadata": {
                        "gstin": outcome["gstin"],
                        "credit_score": assessment.get("credit_score"),
                    },
                }
            )

        cases.sort(key=lambda item: item["similarity"], reverse=True)
        return cases[:k]

    def get_relevant_rules(self, score_payload: Dict[str, Any], k: int = 5) -> List[Dict[str, Any]]:
        rules = self.storage.get_active_apriori_rules()
        return [
            {
                "id": rule["rule_id"],
                "collection": "rules",
                "text": rule["explanation"],
                "similarity": float(rule["confidence"]),
                "metadata": {
                    "doc_type": "apriori_rule",
                    "antecedents": rule["antecedents"],
                    "consequent": rule["consequent"],
                    "support": rule["support"],
                    "confidence": rule["confidence"],
                    "lift": rule["lift"],
                },
            }
            for rule in rules[:k]
        ]

    def get_context_for_question(self, question: str, gstin: str, k: int = 5) -> List[Dict[str, Any]]:
        contexts: List[Dict[str, Any]] = []
        for collection in ("score_history", "rules", "guidelines"):
            result = self.embedding_service.query_similar(collection, question, top_k=k)
            ids = result.get("ids", [[]])[0]
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            for item_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
                contexts.append(
                    {
                        "id": item_id,
                        "collection": collection,
                        "text": text,
                        "metadata": metadata,
                        "similarity": round(1.0 - float(distance), 4),
                    }
                )
        contexts.sort(key=lambda item: item["similarity"], reverse=True)
        return contexts[:k]


@lru_cache(maxsize=1)
def get_retrieval_service() -> RetrievalService:
    return RetrievalService()
