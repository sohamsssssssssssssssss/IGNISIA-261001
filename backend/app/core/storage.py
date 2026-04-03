"""
SQLAlchemy-backed persistence facade for scoring assessments, fraud alerts, and analyst reviews.
Keeps the route-facing API stable while supporting both SQLite and Postgres.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from .database import init_database, session_scope
from .persistence_models import (
    AnalystReviewRecord,
    FraudAlertRecord,
    LoanOutcomeRecord,
    ModelVersionRecord,
    MonitoredGSTINRecord,
    PipelineDataRecord,
    ScoreAssessmentRecord,
)
from .settings import get_settings


class ScoreStorage:
    def __init__(self) -> None:
        init_database()

    def record_assessment(
        self,
        *,
        gstin: str,
        company_name: str,
        credit_score: int,
        risk_band: str,
        fraud_risk: str,
        model_version: str,
        industry_code: str | None,
        months_active: float,
        scenario: str,
        data_sparse: bool,
        freshness_timestamp: str,
        created_at: str,
        top_reasons: List[Dict[str, Any]],
        recommendation: Dict[str, Any],
        source: str = "api",
    ) -> None:
        with session_scope() as session:
            session.add(
                ScoreAssessmentRecord(
                    gstin=gstin,
                    company_name=company_name,
                    credit_score=credit_score,
                    risk_band=risk_band,
                    fraud_risk=fraud_risk,
                    model_version=model_version,
                    industry_code=industry_code,
                    months_active=months_active,
                    scenario=scenario,
                    data_sparse=data_sparse,
                    freshness_timestamp=freshness_timestamp,
                    created_at=created_at,
                    source=source,
                    top_reasons_json=json.dumps(top_reasons),
                    recommendation_json=json.dumps(recommendation),
                )
            )

    def record_fraud_alert(
        self,
        *,
        gstin: str,
        company_name: str,
        circular_risk: str,
        risk_score: int,
        cycle_count: int,
        linked_msme_count: int,
        total_volume: int,
        created_at: str,
        payload: Dict[str, Any],
    ) -> None:
        with session_scope() as session:
            session.add(
                FraudAlertRecord(
                    gstin=gstin,
                    company_name=company_name,
                    circular_risk=circular_risk,
                    risk_score=risk_score,
                    cycle_count=cycle_count,
                    linked_msme_count=linked_msme_count,
                    total_volume=total_volume,
                    created_at=created_at,
                    alert_payload_json=json.dumps(payload),
                )
            )

    def get_score_history(
        self,
        gstin: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        with session_scope() as session:
            stmt = (
                select(
                    ScoreAssessmentRecord.created_at,
                    ScoreAssessmentRecord.credit_score,
                    ScoreAssessmentRecord.risk_band,
                    ScoreAssessmentRecord.fraud_risk,
                    ScoreAssessmentRecord.source,
                    ScoreAssessmentRecord.model_version,
                    ScoreAssessmentRecord.freshness_timestamp,
                )
                .where(ScoreAssessmentRecord.gstin == gstin)
            )
            latest = (
                session.execute(
                    stmt.order_by(ScoreAssessmentRecord.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                .all()
            )

        rows = list(reversed(latest))
        return [
            {
                "timestamp": row.created_at,
                "score": row.credit_score,
                "risk_band": row.risk_band,
                "fraud_risk": row.fraud_risk,
                "source": row.source,
                "model_version": row.model_version,
                "data_freshness": row.freshness_timestamp,
            }
            for row in rows
        ]

    def get_assessment_count(self, gstin: str) -> int:
        with session_scope() as session:
            stmt = select(func.count()).select_from(ScoreAssessmentRecord).where(
                ScoreAssessmentRecord.gstin == gstin
            )
            count = session.scalar(stmt)
        return int(count or 0)

    def get_segment_score_percentile(
        self,
        *,
        credit_score: int,
        months_active: float,
        industry_code: str | None,
    ) -> Dict[str, Any]:
        normalized_industry = "".join(ch for ch in (industry_code or "") if ch.isdigit())[:2] or None
        if months_active < 6:
            age_band = "UNDER_6_MONTHS"
        elif months_active < 12:
            age_band = "MONTHS_6_TO_12"
        elif months_active < 24:
            age_band = "MONTHS_12_TO_24"
        else:
            age_band = "OVER_24_MONTHS"

        def _age_band_filter():
            if age_band == "UNDER_6_MONTHS":
                return ScoreAssessmentRecord.months_active < 6
            if age_band == "MONTHS_6_TO_12":
                return (ScoreAssessmentRecord.months_active >= 6) & (ScoreAssessmentRecord.months_active < 12)
            if age_band == "MONTHS_12_TO_24":
                return (ScoreAssessmentRecord.months_active >= 12) & (ScoreAssessmentRecord.months_active < 24)
            return ScoreAssessmentRecord.months_active >= 24

        with session_scope() as session:
            base_stmt = select(ScoreAssessmentRecord.credit_score).where(_age_band_filter())
            if normalized_industry:
                rows = session.execute(
                    base_stmt.where(ScoreAssessmentRecord.industry_code == normalized_industry)
                ).scalars().all()
                segment_type = "age_and_industry"
                if len(rows) < 5:
                    rows = session.execute(base_stmt).scalars().all()
                    segment_type = "age_band"
            else:
                rows = session.execute(base_stmt).scalars().all()
                segment_type = "age_band"

        scores = sorted(int(v) for v in rows if v is not None)
        if len(scores) < 5:
            percentile = max(1, min(99, int(round(((credit_score - 300) / 600) * 100))))
            sample_size = len(scores)
            segment_type = "fallback_score_scale"
        else:
            below = sum(1 for value in scores if value < credit_score)
            percentile = max(1, min(99, int(round((below / len(scores)) * 100))))
            sample_size = len(scores)

        return {
            "score_percentile": percentile,
            "age_band": age_band,
            "industry_code": normalized_industry,
            "sample_size": sample_size,
            "segment_type": segment_type,
            "statement": (
                f"Better than {percentile}% of MSMEs on the current score scale"
                if segment_type == "fallback_score_scale"
                else (
                    f"Better than {percentile}% of MSMEs in this "
                    f"{'age and sector' if segment_type == 'age_and_industry' else 'age'} group"
                )
            ),
        }

    def get_latest_assessment_model_version(self, gstin: str) -> str | None:
        with session_scope() as session:
            row = session.execute(
                select(ScoreAssessmentRecord.model_version)
                .where(ScoreAssessmentRecord.gstin == gstin)
                .order_by(ScoreAssessmentRecord.created_at.desc())
                .limit(1)
            ).first()
        return row.model_version if row else None

    def record_analyst_review(self, audit_entry: Dict[str, Any]) -> None:
        with session_scope() as session:
            session.add(
                AnalystReviewRecord(
                    session_id=audit_entry["session_id"],
                    company_name=audit_entry["company_name"],
                    analyst_action=audit_entry["analyst_action"],
                    original_score=audit_entry["original_score"],
                    adjusted_score=audit_entry["adjusted_score"],
                    total_adjustment=audit_entry["total_adjustment"],
                    original_verdict=audit_entry["original_verdict"],
                    adjusted_verdict=audit_entry["adjusted_verdict"],
                    management_quality=audit_entry.get("management_quality"),
                    factory_utilization=audit_entry.get("factory_utilization"),
                    field_notes=audit_entry.get("field_notes"),
                    created_at=audit_entry["timestamp"],
                    payload_json=json.dumps(audit_entry),
                )
            )

    def get_analyst_reviews(self, session_id: str) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = (
                session.execute(
                    select(AnalystReviewRecord.payload_json)
                    .where(AnalystReviewRecord.session_id == session_id)
                    .order_by(AnalystReviewRecord.created_at.asc())
                )
                .all()
            )
        return [json.loads(row.payload_json) for row in rows]

    def record_loan_outcome(
        self,
        *,
        gstin: str,
        company_name: str | None,
        repaid: bool,
        loan_amount: float,
        tenure_months: int,
        recorded_at: str,
        source_model_version: str | None,
        feature_snapshot: Dict[str, Any],
    ) -> None:
        with session_scope() as session:
            session.add(
                LoanOutcomeRecord(
                    gstin=gstin,
                    company_name=company_name,
                    repaid=repaid,
                    loan_amount=loan_amount,
                    tenure_months=tenure_months,
                    recorded_at=recorded_at,
                    source_model_version=source_model_version,
                    feature_snapshot_json=json.dumps(feature_snapshot),
                )
            )

    def count_loan_outcomes(self) -> int:
        with session_scope() as session:
            count = session.scalar(select(func.count()).select_from(LoanOutcomeRecord))
        return int(count or 0)

    def get_loan_outcomes(self) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(
                select(
                    LoanOutcomeRecord.gstin,
                    LoanOutcomeRecord.company_name,
                    LoanOutcomeRecord.repaid,
                    LoanOutcomeRecord.loan_amount,
                    LoanOutcomeRecord.tenure_months,
                    LoanOutcomeRecord.recorded_at,
                    LoanOutcomeRecord.source_model_version,
                    LoanOutcomeRecord.feature_snapshot_json,
                ).order_by(LoanOutcomeRecord.recorded_at.asc())
            ).all()
        return [
            {
                "gstin": row.gstin,
                "company_name": row.company_name,
                "repaid": row.repaid,
                "loan_amount": row.loan_amount,
                "tenure_months": row.tenure_months,
                "recorded_at": row.recorded_at,
                "source_model_version": row.source_model_version,
                "feature_snapshot": json.loads(row.feature_snapshot_json),
            }
            for row in rows
        ]

    def record_model_version(
        self,
        *,
        model_version: str,
        trained_at: str,
        training_sample_size: int,
        synthetic_sample_count: int,
        real_sample_count: int,
        real_label_ratio: float,
        auc_before: float | None,
        auc_after: float | None,
        feature_schema_version: str,
        metrics: Dict[str, Any],
    ) -> None:
        with session_scope() as session:
            session.add(
                ModelVersionRecord(
                    model_version=model_version,
                    trained_at=trained_at,
                    training_sample_size=training_sample_size,
                    synthetic_sample_count=synthetic_sample_count,
                    real_sample_count=real_sample_count,
                    real_label_ratio=real_label_ratio,
                    auc_before=auc_before,
                    auc_after=auc_after,
                    feature_schema_version=feature_schema_version,
                    metrics_json=json.dumps(metrics),
                )
            )

    def get_model_versions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(
                select(
                    ModelVersionRecord.model_version,
                    ModelVersionRecord.trained_at,
                    ModelVersionRecord.training_sample_size,
                    ModelVersionRecord.synthetic_sample_count,
                    ModelVersionRecord.real_sample_count,
                    ModelVersionRecord.real_label_ratio,
                    ModelVersionRecord.auc_before,
                    ModelVersionRecord.auc_after,
                    ModelVersionRecord.feature_schema_version,
                    ModelVersionRecord.metrics_json,
                )
                .order_by(ModelVersionRecord.trained_at.desc())
                .limit(limit)
            ).all()
        return [
            {
                "model_version": row.model_version,
                "trained_at": row.trained_at,
                "training_sample_size": row.training_sample_size,
                "synthetic_sample_count": row.synthetic_sample_count,
                "real_sample_count": row.real_sample_count,
                "real_label_ratio": row.real_label_ratio,
                "auc_before": row.auc_before,
                "auc_after": row.auc_after,
                "feature_schema_version": row.feature_schema_version,
                "metrics": json.loads(row.metrics_json),
            }
            for row in rows
        ]

    # ── Pipeline data store ────────────────────────────────

    def store_pipeline_data(
        self,
        *,
        gstin: str,
        pipeline_type: str,
        epoch: int,
        data: Dict[str, Any],
        ingested_at: str,
    ) -> None:
        """Upsert the latest pipeline snapshot for a (gstin, pipeline_type)."""
        with session_scope() as session:
            existing = session.execute(
                select(PipelineDataRecord)
                .where(PipelineDataRecord.gstin == gstin)
                .where(PipelineDataRecord.pipeline_type == pipeline_type)
            ).scalar_one_or_none()

            if existing:
                existing.epoch = epoch
                existing.data_json = json.dumps(data)
                existing.ingested_at = ingested_at
            else:
                session.add(
                    PipelineDataRecord(
                        gstin=gstin,
                        pipeline_type=pipeline_type,
                        epoch=epoch,
                        ingested_at=ingested_at,
                        data_json=json.dumps(data),
                    )
                )

    def get_pipeline_data(self, gstin: str) -> Dict[str, Any] | None:
        """
        Return the latest pipeline data for all three streams for a GSTIN.
        Returns None if any of the three pipelines hasn't ingested yet.
        """
        types = ("gst_velocity", "upi_cadence", "eway_bill")
        result: Dict[str, Any] = {"gstin": gstin, "pipeline_ingested_at": {}}
        with session_scope() as session:
            for pt in types:
                row = session.execute(
                    select(PipelineDataRecord.data_json, PipelineDataRecord.ingested_at)
                    .where(PipelineDataRecord.gstin == gstin)
                    .where(PipelineDataRecord.pipeline_type == pt)
                ).one_or_none()
                if row is None:
                    return None
                result[pt] = json.loads(row.data_json)
                result["pipeline_ingested_at"][pt] = row.ingested_at
            # Use the oldest ingested_at as pipeline_timestamp
            oldest = session.execute(
                select(func.min(PipelineDataRecord.ingested_at))
                .where(PipelineDataRecord.gstin == gstin)
            ).scalar()
            result["pipeline_timestamp"] = oldest
        return result

    def get_pipeline_freshness(self, gstin: str) -> str | None:
        """Return the oldest ingested_at across the three pipelines for a GSTIN."""
        with session_scope() as session:
            oldest = session.execute(
                select(func.min(PipelineDataRecord.ingested_at))
                .where(PipelineDataRecord.gstin == gstin)
            ).scalar()
        return oldest

    def get_pipeline_epoch(self, gstin: str, pipeline_type: str) -> int:
        """Return the current epoch for a (gstin, pipeline_type), or 0 if none."""
        with session_scope() as session:
            epoch = session.execute(
                select(PipelineDataRecord.epoch)
                .where(PipelineDataRecord.gstin == gstin)
                .where(PipelineDataRecord.pipeline_type == pipeline_type)
            ).scalar()
        return int(epoch) if epoch is not None else 0

    # ── Monitored GSTIN registry ─────────────────────────

    def register_gstin(self, gstin: str, company_name: str | None = None) -> bool:
        """Add a GSTIN to the monitored set. Returns True if newly added."""
        from datetime import datetime, timezone
        with session_scope() as session:
            exists = session.execute(
                select(MonitoredGSTINRecord.gstin)
                .where(MonitoredGSTINRecord.gstin == gstin)
            ).scalar()
            if exists:
                return False
            session.add(
                MonitoredGSTINRecord(
                    gstin=gstin,
                    company_name=company_name,
                    added_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                )
            )
        return True

    def get_monitored_gstins(self) -> List[str]:
        """Return all GSTINs the workers should generate data for."""
        with session_scope() as session:
            rows = session.execute(
                select(MonitoredGSTINRecord.gstin)
                .order_by(MonitoredGSTINRecord.added_at.asc())
            ).all()
        return [r.gstin for r in rows]

    def health_summary(self) -> Dict[str, Any]:
        settings = get_settings()
        url = make_url(settings.database_url)
        safe_url = url.render_as_string(hide_password=True)
        with session_scope() as session:
            assessments = session.scalar(select(func.count()).select_from(ScoreAssessmentRecord)) or 0
            alerts = session.scalar(select(func.count()).select_from(FraudAlertRecord)) or 0
            reviews = session.scalar(select(func.count()).select_from(AnalystReviewRecord)) or 0
            outcomes = session.scalar(select(func.count()).select_from(LoanOutcomeRecord)) or 0
            versions = session.scalar(select(func.count()).select_from(ModelVersionRecord)) or 0

        return {
            "database_url": safe_url,
            "database_path": url.database if safe_url.startswith("sqlite") else None,
            "database_backend": url.get_backend_name(),
            "score_assessments": int(assessments),
            "fraud_alerts": int(alerts),
            "analyst_reviews": int(reviews),
            "loan_outcomes": int(outcomes),
            "model_versions": int(versions),
        }


_storage: ScoreStorage | None = None


def get_storage() -> ScoreStorage:
    global _storage
    if _storage is None:
        _storage = ScoreStorage()
    return _storage
