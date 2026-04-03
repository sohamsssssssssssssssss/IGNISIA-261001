"""
Apriori association-rule mining over historical scored outcomes.
Generates outcome-linked lending rules and embeds them into the RAG rule store.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List

from ..services.embedding_service import get_embedding_service
from ..services.llm_client import llm
from ..core.storage import get_storage

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency in some envs
    pd = None

try:
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder
except ImportError:  # pragma: no cover - optional dependency in some envs
    apriori = None
    association_rules = None
    TransactionEncoder = None


RULE_CACHE_TTL = timedelta(hours=1)
MIN_HISTORY_FOR_RULES = 50


class AprioriService:
    def __init__(self) -> None:
        self.storage = get_storage()
        self.embedding_service = get_embedding_service()
        self._cache: List[Dict[str, Any]] = []
        self._cache_generated_at: datetime | None = None
        self._lock = threading.Lock()
        self._refresh_in_progress = False

    def discretize_features(self, score_payload: Dict[str, Any]) -> List[str]:
        feature_vector = score_payload.get("feature_vector") or score_payload.get("feature_snapshot") or {}
        fraud = score_payload.get("fraud_detection") or {}
        items: List[str] = []

        if feature_vector.get("gst_filing_rate", 0.0) > 0.9:
            items.append("high_gst_compliance")
        if feature_vector.get("history_months_active", 0.0) > 12:
            items.append("mature_business")
        if feature_vector.get("upi_regularity_score", 0.0) > 80:
            items.append("regular_upi_cadence")
        if feature_vector.get("overall_data_confidence", 0.0) >= 0.8:
            items.append("high_data_confidence")
        if feature_vector.get("overall_data_confidence", 1.0) < 0.5:
            items.append("low_data_confidence")
        if feature_vector.get("upi_round_amount_pct", 0.0) < 20:
            items.append("no_fraud_flags")
        if feature_vector.get("upi_round_amount_pct", 0.0) >= 30:
            items.append("round_amount_cluster")

        fraud_score = float(fraud.get("risk_score", 0.0) or 0.0)
        if fraud_score < 20:
            items.append("no_fraud_flags")
        if fraud_score >= 60:
            items.append("high_fraud_score")

        if str((score_payload.get("risk_band") or {}).get("band") or score_payload.get("risk_band") or "").upper() in {
            "LOW_RISK",
            "VERY_LOW_RISK",
        }:
            items.append("low_risk_band")
        if str((score_payload.get("risk_band") or {}).get("band") or score_payload.get("risk_band") or "").upper() in {
            "HIGH_RISK",
            "VERY_HIGH_RISK",
        }:
            items.append("high_risk_band")

        credit_score = float(score_payload.get("credit_score", 0.0) or 0.0)
        if credit_score > 750:
            items.append("high_credit_score")
        if credit_score < 550:
            items.append("weak_credit_score")

        industry_code = str(score_payload.get("industry_code") or "")
        if industry_code.startswith(("10", "13", "17")):
            items.append("manufacturing_sector")
        if industry_code.startswith("62"):
            items.append("technology_services_sector")
        if industry_code.startswith("49"):
            items.append("logistics_sector")

        months_active = float(feature_vector.get("history_months_active", score_payload.get("months_active", 0.0)) or 0.0)
        if months_active < 6:
            items.append("young_business")

        outcome = score_payload.get("outcome")
        if outcome == "repaid":
            items.append("repaid")
        elif outcome == "defaulted":
            items.append("defaulted")

        return sorted(set(items))

    def run_apriori(
        self,
        min_support: float = 0.1,
        min_confidence: float = 0.6,
        *,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if not force and self._cache_generated_at and datetime.now(timezone.utc) - self._cache_generated_at < RULE_CACHE_TTL:
                return list(self._cache)
            if not force:
                persisted = self.storage.get_active_apriori_rules()
                persisted_generated_at = self.storage.get_latest_apriori_rule_created_at()
                if persisted and persisted_generated_at:
                    generated_at = self._parse_timestamp(persisted_generated_at)
                    if generated_at and datetime.now(timezone.utc) - generated_at < RULE_CACHE_TTL:
                        self._cache = persisted
                        self._cache_generated_at = generated_at
                        return list(self._cache)
            self._refresh_in_progress = True

        try:
            rules = self._compute_rules(min_support=min_support, min_confidence=min_confidence)
            generated_at = datetime.now(timezone.utc)
            self.storage.replace_apriori_rules(
                rules,
                created_at=generated_at.isoformat().replace("+00:00", "Z"),
            )
            self.embed_rules(rules)
            with self._lock:
                self._cache = rules
                self._cache_generated_at = generated_at
            return list(rules)
        finally:
            with self._lock:
                self._refresh_in_progress = False

    def generate_rule_explanation(self, rule: Dict[str, Any]) -> str:
        antecedents = ", ".join(rule["antecedents"])
        consequent = rule["consequent"]
        prompt = (
            "Explain this lending rule in one plain English sentence that a loan officer "
            "with no data science background can understand and act on. Start with "
            "\"Businesses that...\"\n\n"
            f"Antecedents: {antecedents}\n"
            f"Consequent: {consequent}\n"
            f"Support: {rule['support']:.2f}\n"
            f"Confidence: {rule['confidence']:.2f}\n"
            f"Lift: {rule['lift']:.2f}"
        )
        try:
            explanation = llm.generate_sync(prompt, max_tokens=120).strip()
            if explanation.lower().startswith("businesses that"):
                return explanation
        except Exception:
            pass

        outcome_phrase = "repay loans" if consequent == "repaid" else "tend to default"
        return (
            f"Businesses that {antecedents.replace('_', ' ')} {outcome_phrase} "
            f"{int(round(rule['confidence'] * 100))}% of the time in our assessment history."
        )

    def embed_rules(self, rules: List[Dict[str, Any]] | None = None) -> None:
        candidate_rules = rules if rules is not None else self._cache
        for rule in candidate_rules:
            rule_id = rule["rule_id"]
            rule_text = (
                f"Association rule: if {' and '.join(rule['antecedents'])}, then {rule['consequent']}. "
                f"Support={rule['support']:.3f}, confidence={rule['confidence']:.3f}, lift={rule['lift']:.3f}. "
                f"Explanation: {rule['explanation']}"
            )
            self.embedding_service.embed_rule(
                rule_id,
                rule_text,
                {
                    "rule_type": "apriori_rule",
                    "consequent": rule["consequent"],
                    "support": rule["support"],
                    "confidence": rule["confidence"],
                    "lift": rule["lift"],
                    "antecedents": rule["antecedents"],
                },
            )

    def get_rules(self, *, force_refresh: bool = False) -> List[Dict[str, Any]]:
        return self.run_apriori(force=force_refresh)

    def rules_are_stale(self) -> bool:
        with self._lock:
            return self._cache_is_stale_locked()

    def trigger_refresh_async_if_needed(self) -> None:
        if self.storage.count_assessments() < MIN_HISTORY_FOR_RULES:
            return
        with self._lock:
            if self._refresh_in_progress or not self._cache_is_stale_locked():
                return
            self._refresh_in_progress = True

        def _runner():
            try:
                self.run_apriori(force=True)
            finally:
                with self._lock:
                    self._refresh_in_progress = False

        threading.Thread(target=_runner, daemon=True).start()

    def get_cache_metadata(self) -> Dict[str, Any]:
        with self._lock:
            if self._cache_generated_at is None:
                persisted_generated_at = self.storage.get_latest_apriori_rule_created_at()
                if persisted_generated_at:
                    self._cache_generated_at = self._parse_timestamp(persisted_generated_at)
                if not self._cache:
                    self._cache = self.storage.get_active_apriori_rules()
            return {
                "generated_at": self._cache_generated_at.isoformat().replace("+00:00", "Z")
                if self._cache_generated_at
                else None,
                "rule_count": len(self._cache),
                "stale": self._cache_is_stale_locked(),
            }

    def _compute_rules(self, *, min_support: float, min_confidence: float) -> List[Dict[str, Any]]:
        if pd is None or apriori is None or association_rules is None or TransactionEncoder is None:
            return []

        outcomes = self.storage.get_loan_outcomes()
        transactions: List[List[str]] = []
        for outcome in outcomes:
            assessment = self.storage.get_latest_assessment_details(outcome["gstin"])
            if assessment is None:
                continue
            fraud = self.storage.get_latest_fraud_alert(outcome["gstin"]) or {
                "risk_score": 0,
                "circular_risk": assessment.get("fraud_risk"),
            }
            transaction = self.discretize_features(
                {
                    "feature_snapshot": outcome.get("feature_snapshot") or {},
                    "fraud_detection": fraud,
                    "credit_score": assessment.get("credit_score"),
                    "risk_band": {"band": assessment.get("risk_band")},
                    "industry_code": assessment.get("industry_code"),
                    "months_active": assessment.get("months_active"),
                    "outcome": "repaid" if outcome.get("repaid") else "defaulted",
                }
            )
            if len(transaction) >= 2:
                transactions.append(transaction)

        if len(transactions) < MIN_HISTORY_FOR_RULES:
            return []

        encoder = TransactionEncoder()
        encoded = encoder.fit(transactions).transform(transactions)
        frame = pd.DataFrame(encoded, columns=encoder.columns_)

        frequent_itemsets = apriori(frame, min_support=min_support, use_colnames=True)
        if frequent_itemsets.empty:
            return []

        rules_frame = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_confidence)
        if rules_frame.empty:
            return []

        filtered = rules_frame[
            rules_frame["consequents"].apply(
                lambda value: len(value) == 1 and next(iter(value)) in {"repaid", "defaulted"}
            )
        ]
        if filtered.empty:
            return []

        filtered = filtered.sort_values(by=["confidence", "lift", "support"], ascending=False)
        rules: List[Dict[str, Any]] = []
        for _, row in filtered.iterrows():
            antecedents = sorted(str(item) for item in row["antecedents"])
            consequent = next(iter(row["consequents"]))
            rule = {
                "rule_id": self._rule_id(antecedents, consequent),
                "antecedents": antecedents,
                "consequent": consequent,
                "support": round(float(row["support"]), 4),
                "confidence": round(float(row["confidence"]), 4),
                "lift": round(float(row["lift"]), 4),
            }
            rule["explanation"] = self.generate_rule_explanation(rule)
            rules.append(rule)
            if len(rules) >= 25:
                break
        return rules

    def _rule_id(self, antecedents: List[str], consequent: str) -> str:
        digest = hashlib.sha1(
            json.dumps({"antecedents": antecedents, "consequent": consequent}, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        return f"apriori-{digest}"

    def _cache_is_stale_locked(self) -> bool:
        if self._cache_generated_at is None:
            persisted_generated_at = self.storage.get_latest_apriori_rule_created_at()
            if persisted_generated_at:
                self._cache_generated_at = self._parse_timestamp(persisted_generated_at)
                if not self._cache:
                    self._cache = self.storage.get_active_apriori_rules()
            else:
                return True
        return datetime.now(timezone.utc) - self._cache_generated_at >= RULE_CACHE_TTL

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None


@lru_cache(maxsize=1)
def get_apriori_service() -> AprioriService:
    return AprioriService()
