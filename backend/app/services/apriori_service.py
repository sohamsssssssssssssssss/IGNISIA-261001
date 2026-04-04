"""
Behavioral pattern intelligence built on Apriori association-rule mining.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List

from ..core.storage import get_storage
from .apriori_constants import (
    APRIORI_CACHE_TTL_SECONDS,
    APRIORI_MIN_CONFIDENCE,
    APRIORI_MIN_SUPPORT,
    APRIORI_TOP_RULES_LIMIT,
    BUSINESS_MATURE_THRESHOLD_MONTHS,
    BUSINESS_NEW_THRESHOLD_MONTHS,
    CREDIT_HIGH_SCORE_THRESHOLD,
    CREDIT_MEDIUM_SCORE_THRESHOLD,
    EWB_HIGH_ACTIVITY_THRESHOLD,
    GST_HIGH_THRESHOLD,
    GST_LOW_THRESHOLD,
    ITEM_DESCRIPTION_MAP,
    MIN_OUTCOME_LABELED_RECORDS,
    UPI_IRREGULAR_THRESHOLD,
    UPI_REGULAR_THRESHOLD,
)

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

try:
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder
except ImportError:  # pragma: no cover
    apriori = None
    association_rules = None
    TransactionEncoder = None


logger = logging.getLogger("intellicredit.apriori")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AprioriService:
    def __init__(self) -> None:
        self.storage = get_storage()
        self._cache: List[Dict[str, Any]] = []
        self._cache_generated_at: datetime | None = None
        self._lock = threading.Lock()
        self._refresh_in_progress = False

    def discretize_features(self, score_payload: Dict[str, Any]) -> List[str]:
        feature_snapshot = score_payload.get("feature_snapshot") or {}
        pipeline_data = score_payload.get("pipeline_data") or {}
        fraud_detection = score_payload.get("fraud_detection") or {}

        gst_rate_raw = feature_snapshot.get("gst_filing_rate")
        if gst_rate_raw is None:
            gst_rate_raw = pipeline_data.get("gst_velocity", {}).get("velocity_metrics", {}).get("filings_per_month", 0.0)
        gst_rate = float(gst_rate_raw or 0.0)
        if gst_rate > 1.0:
            gst_rate /= 100.0

        upi_regularity_raw = feature_snapshot.get("upi_regularity_score")
        if upi_regularity_raw is None:
            upi_regularity_raw = pipeline_data.get("upi_cadence", {}).get("cadence_metrics", {}).get("regularity_score", 0.0)
        upi_regularity = float(upi_regularity_raw or 0.0)
        if upi_regularity > 1.0:
            upi_regularity /= 100.0

        months_active = float(
            feature_snapshot.get("history_months_active")
            or score_payload.get("months_active")
            or pipeline_data.get("gst_velocity", {}).get("months_active")
            or 0.0
        )

        fraud_score = float(fraud_detection.get("risk_score") or 0.0)
        has_fraud_flag = fraud_score > 40 or str(score_payload.get("fraud_risk") or "").upper() in {"HIGH", "MEDIUM"}

        ewb_activity = float(
            feature_snapshot.get("eway_avg_monthly_bills")
            or pipeline_data.get("eway_bill", {}).get("trend_metrics", {}).get("avg_bills_per_month")
            or 0.0
        )
        credit_score = float(score_payload.get("credit_score") or 0.0)
        outcome = str(score_payload.get("outcome") or "").strip().lower()

        items: List[str] = []

        if gst_rate > GST_HIGH_THRESHOLD:
            items.append("high_gst_compliance")
        elif gst_rate < GST_LOW_THRESHOLD:
            items.append("low_gst_compliance")
        else:
            items.append("medium_gst_compliance")

        if upi_regularity > UPI_REGULAR_THRESHOLD:
            items.append("regular_upi_cadence")
        elif upi_regularity < UPI_IRREGULAR_THRESHOLD:
            items.append("irregular_upi_cadence")
        else:
            items.append("moderate_upi_cadence")

        if months_active > BUSINESS_MATURE_THRESHOLD_MONTHS:
            items.append("mature_business")
        elif months_active < BUSINESS_NEW_THRESHOLD_MONTHS:
            items.append("new_business")
        else:
            items.append("established_business")

        items.append("fraud_flagged" if has_fraud_flag else "clean_profile")
        items.append("high_ewb_activity" if ewb_activity >= EWB_HIGH_ACTIVITY_THRESHOLD else "low_ewb_activity")

        if credit_score > CREDIT_HIGH_SCORE_THRESHOLD:
            items.append("high_score")
        elif credit_score < CREDIT_MEDIUM_SCORE_THRESHOLD:
            items.append("low_score")
        else:
            items.append("medium_score")

        if outcome in {"repaid", "defaulted"}:
            items.append(outcome)

        return items

    def get_rules(self, *, force_refresh: bool = False) -> List[Dict[str, Any]]:
        return self.run_apriori(force=force_refresh)

    def run_apriori(
        self,
        min_support: float = APRIORI_MIN_SUPPORT,
        min_confidence: float = APRIORI_MIN_CONFIDENCE,
        *,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if not force and self._cache and self._cache_generated_at and not self._cache_is_stale_locked():
                return list(self._cache)
            if not force and not self._cache:
                persisted = self.storage.get_active_apriori_rules()
                if persisted:
                    generated_at = self._parse_timestamp(persisted[0].get("generated_at"))
                    self._cache = persisted
                    self._cache_generated_at = generated_at
                    if not self._cache_is_stale_locked():
                        return list(self._cache)
            self._refresh_in_progress = True

        try:
            rules = self._compute_rules(min_support=min_support, min_confidence=min_confidence)
            generated_at = _utc_now().isoformat().replace("+00:00", "Z")
            self.storage.replace_apriori_rules(rules, created_at=generated_at)
            with self._lock:
                self._cache = rules
                self._cache_generated_at = self._parse_timestamp(generated_at)
            return list(rules)
        finally:
            with self._lock:
                self._refresh_in_progress = False

    def rules_are_stale(self) -> bool:
        with self._lock:
            return self._cache_is_stale_locked()

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = []
            self._cache_generated_at = None

    def get_cache_metadata(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "generated_at": self._cache_generated_at.isoformat().replace("+00:00", "Z")
                if self._cache_generated_at
                else None,
                "rule_count": len(self._cache),
                "stale": self._cache_is_stale_locked(),
                "ttl_seconds": APRIORI_CACHE_TTL_SECONDS,
            }

    def get_matching_rules(
        self,
        feature_items: List[str],
        outcome: str,
        top_n: int = 2,
    ) -> List[Dict[str, Any]]:
        if not feature_items or outcome not in {"repaid", "defaulted"}:
            return []

        feature_item_set = set(feature_items)
        matching = [
            rule
            for rule in self.get_rules()
            if rule["consequent"] == outcome and set(rule["antecedents"]).issubset(feature_item_set)
        ]
        matching.sort(key=lambda rule: (-float(rule["lift"]), -float(rule["confidence"]), -int(rule["record_count"])))
        return matching[:top_n]

    def get_matching_rules_for_gstin(
        self,
        gstin: str,
        *,
        outcome: str | None = None,
        top_n: int = 2,
    ) -> List[Dict[str, Any]]:
        record = self._build_scoring_record_for_gstin(gstin)
        if record is None:
            return []
        inferred_outcome = outcome or self._infer_outcome_from_record(record)
        return self.get_matching_rules(self.discretize_features(record), inferred_outcome, top_n=top_n)

    def has_minimum_records(self) -> bool:
        return self._ensure_outcome_labels() >= MIN_OUTCOME_LABELED_RECORDS

    def trigger_refresh_async_if_needed(self) -> None:
        if not self.has_minimum_records():
            return
        with self._lock:
            if self._refresh_in_progress or not self._cache_is_stale_locked():
                return
            self._refresh_in_progress = True

        def _runner():
            try:
                self.run_apriori(force=True)
            except Exception:
                logger.exception("Apriori refresh failed")
            finally:
                with self._lock:
                    self._refresh_in_progress = False

        threading.Thread(target=_runner, daemon=True).start()

    def run_refresh_job(self) -> None:
        if not self.has_minimum_records():
            logger.info("Skipping Apriori mining refresh; not enough outcome-labeled records")
            return
        self.run_apriori(force=True)

    def _compute_rules(self, *, min_support: float, min_confidence: float) -> List[Dict[str, Any]]:
        if pd is None or apriori is None or association_rules is None or TransactionEncoder is None:
            logger.warning("Apriori dependencies unavailable; returning empty rule set")
            return []

        labeled_count = self._ensure_outcome_labels()
        if labeled_count < MIN_OUTCOME_LABELED_RECORDS:
            logger.warning("Apriori skipped with only %s outcome-labeled records", labeled_count)
            return []

        rule_records = self.storage.get_rule_mining_records()
        transactions = [self.discretize_features(record) for record in rule_records]
        transactions = [transaction for transaction in transactions if "repaid" in transaction or "defaulted" in transaction]
        if len(transactions) < MIN_OUTCOME_LABELED_RECORDS:
            logger.warning("Apriori skipped after record join; only %s usable transactions", len(transactions))
            return []

        encoder = TransactionEncoder()
        frame = pd.DataFrame(encoder.fit(transactions).transform(transactions), columns=encoder.columns_)

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

        filtered = filtered.sort_values(by=["lift", "confidence"], ascending=False)
        generated_at = _utc_now().isoformat().replace("+00:00", "Z")
        results: List[Dict[str, Any]] = []

        for _, row in filtered.iterrows():
            antecedents = sorted(str(item) for item in row["antecedents"])
            consequent = str(next(iter(row["consequents"])))
            support = round(float(row["support"]), 4)
            confidence = round(float(row["confidence"]), 4)
            lift = round(float(row["lift"]), 4)
            record_count = max(1, int(round(support * len(transactions))))
            rule = {
                "id": self._rule_id(antecedents, consequent),
                "antecedents": antecedents,
                "consequent": consequent,
                "support": support,
                "confidence": confidence,
                "lift": lift,
                "record_count": record_count,
                "explanation": self.generate_rule_explanation(
                    {
                        "antecedents": antecedents,
                        "consequent": consequent,
                        "confidence": confidence,
                        "record_count": record_count,
                    }
                ),
                "generated_at": generated_at,
            }
            results.append(rule)
            if len(results) >= APRIORI_TOP_RULES_LIMIT:
                break

        return results

    def generate_rule_explanation(self, rule: Dict[str, Any]) -> str:
        phrases = [ITEM_DESCRIPTION_MAP.get(item, item.replace("_", " ")) for item in rule["antecedents"]]
        if not phrases:
            antecedents_text = "match this profile"
        elif len(phrases) == 1:
            antecedents_text = phrases[0]
        elif len(phrases) == 2:
            antecedents_text = f"{phrases[0]} and {phrases[1]}"
        else:
            antecedents_text = ", ".join(phrases[:-1]) + f", and {phrases[-1]}"

        action = "repay" if rule["consequent"] == "repaid" else "default on"
        return (
            f"Businesses that {antecedents_text} {action} loans "
            f"{int(round(float(rule['confidence']) * 100))}% of the time, "
            f"based on {int(rule['record_count'])} similar cases."
        )

    def _build_scoring_record_for_gstin(self, gstin: str) -> Dict[str, Any] | None:
        assessment = self.storage.get_latest_assessment_details(gstin)
        if assessment is None:
            return None
        return {
            "gstin": gstin,
            "credit_score": assessment.get("credit_score"),
            "risk_band": assessment.get("risk_band"),
            "months_active": assessment.get("months_active"),
            "fraud_risk": assessment.get("fraud_risk"),
            "fraud_detection": self.storage.get_latest_fraud_alert(gstin) or {},
            "pipeline_data": self.storage.get_pipeline_data(gstin) or {},
            "feature_snapshot": {},
            "outcome": self._infer_outcome_from_record(assessment),
        }

    def _infer_outcome_from_record(self, record: Dict[str, Any]) -> str:
        recommendation = record.get("recommendation") or {}
        if bool(recommendation.get("eligible")):
            return "repaid"
        credit_score = float(record.get("credit_score") or 0.0)
        return "repaid" if credit_score >= CREDIT_MEDIUM_SCORE_THRESHOLD else "defaulted"

    def _ensure_outcome_labels(self) -> int:
        labeled_count = self.storage.count_distinct_outcome_labeled_gstins()
        if labeled_count >= MIN_OUTCOME_LABELED_RECORDS:
            return labeled_count
        seed_status = self.storage.ensure_mock_loan_outcomes_for_latest_assessments()
        logger.info("Apriori mock outcome seeding complete: %s", seed_status)
        return self.storage.count_distinct_outcome_labeled_gstins()

    def _rule_id(self, antecedents: List[str], consequent: str) -> str:
        digest = hashlib.sha1(
            json.dumps({"antecedents": antecedents, "consequent": consequent}, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        return f"rule-{digest}"

    def _cache_is_stale_locked(self) -> bool:
        if self._cache_generated_at is None:
            return True
        return _utc_now() - self._cache_generated_at >= timedelta(seconds=APRIORI_CACHE_TTL_SECONDS)

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


@lru_cache(maxsize=1)
def get_apriori_service() -> AprioriService:
    return AprioriService()
