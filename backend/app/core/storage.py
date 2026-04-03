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
    AprioriRuleRecord,
    ChatMessageRecord,
    ChatSessionRecord,
    DocumentSessionRecord,
    FraudAlertRecord,
    LoanOutcomeRecord,
    ModelVersionRecord,
    MonitoredGSTINRecord,
    PipelineDataRecord,
    PipelineRunEventRecord,
    PipelineRunRecord,
    ScoreAssessmentRecord,
    UploadedDocumentRecord,
)
from .settings import get_settings

_UNSET = object()


class ScoreStorage:
    def __init__(self) -> None:
        init_database()

    def create_document_session(
        self,
        *,
        session_id: str,
        created_at: str,
        updated_at: str,
        workflow_status: str = "uploaded",
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        with session_scope() as session:
            existing = session.execute(
                select(DocumentSessionRecord)
                .where(DocumentSessionRecord.session_id == session_id)
                .limit(1)
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    DocumentSessionRecord(
                        session_id=session_id,
                        created_at=created_at,
                        updated_at=updated_at,
                        workflow_status=workflow_status,
                        metadata_json=json.dumps(metadata or {}),
                    )
                )
                return

            existing.updated_at = updated_at
            existing.workflow_status = workflow_status
            existing.metadata_json = json.dumps(metadata or json.loads(existing.metadata_json or "{}"))

    def get_document_session(self, session_id: str) -> Dict[str, Any] | None:
        with session_scope() as session:
            row = session.execute(
                select(
                    DocumentSessionRecord.session_id,
                    DocumentSessionRecord.created_at,
                    DocumentSessionRecord.updated_at,
                    DocumentSessionRecord.workflow_status,
                    DocumentSessionRecord.company_name,
                    DocumentSessionRecord.metadata_json,
                    DocumentSessionRecord.last_error,
                    DocumentSessionRecord.cam_filename,
                    DocumentSessionRecord.cam_file_path,
                )
                .where(DocumentSessionRecord.session_id == session_id)
                .limit(1)
            ).first()
        if row is None:
            return None
        return {
            "session_id": row.session_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "workflow_status": row.workflow_status,
            "company_name": row.company_name,
            "metadata": json.loads(row.metadata_json or "{}"),
            "last_error": row.last_error,
            "cam_filename": row.cam_filename,
            "cam_file_path": row.cam_file_path,
        }

    def update_document_session(
        self,
        session_id: str,
        *,
        updated_at: str,
        workflow_status: str | None = None,
        company_name: str | None = None,
        metadata: Dict[str, Any] | None = None,
        last_error: str | None | object = _UNSET,
        cam_filename: str | None = None,
        cam_file_path: str | None = None,
    ) -> bool:
        with session_scope() as session:
            record = session.execute(
                select(DocumentSessionRecord)
                .where(DocumentSessionRecord.session_id == session_id)
                .limit(1)
            ).scalar_one_or_none()
            if record is None:
                return False
            record.updated_at = updated_at
            if workflow_status is not None:
                record.workflow_status = workflow_status
            if company_name is not None:
                record.company_name = company_name
            if metadata is not None:
                record.metadata_json = json.dumps(metadata)
            if last_error is not _UNSET:
                record.last_error = last_error
            if cam_filename is not None:
                record.cam_filename = cam_filename
            if cam_file_path is not None:
                record.cam_file_path = cam_file_path
            return True

    def add_uploaded_documents(
        self,
        session_id: str,
        documents: List[Dict[str, Any]],
    ) -> None:
        with session_scope() as session:
            for document in documents:
                session.add(
                    UploadedDocumentRecord(
                        session_id=session_id,
                        filename=document["filename"],
                        file_path=document["file_path"],
                        predicted_type=document["predicted_type"],
                        confidence=float(document["confidence"]),
                        evidence=document["evidence"],
                        confirmed_type=document.get("confirmed_type"),
                        status=document.get("status", "PENDING"),
                        uploaded_at=document["uploaded_at"],
                    )
                )

    def list_uploaded_documents(self, session_id: str) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(
                select(
                    UploadedDocumentRecord.id,
                    UploadedDocumentRecord.session_id,
                    UploadedDocumentRecord.filename,
                    UploadedDocumentRecord.file_path,
                    UploadedDocumentRecord.predicted_type,
                    UploadedDocumentRecord.confidence,
                    UploadedDocumentRecord.evidence,
                    UploadedDocumentRecord.confirmed_type,
                    UploadedDocumentRecord.status,
                    UploadedDocumentRecord.uploaded_at,
                )
                .where(UploadedDocumentRecord.session_id == session_id)
                .order_by(UploadedDocumentRecord.id.asc())
            ).all()
        return [
            {
                "id": row.id,
                "session_id": row.session_id,
                "filename": row.filename,
                "file_path": row.file_path,
                "predicted_type": row.predicted_type,
                "confidence": row.confidence,
                "evidence": row.evidence,
                "confirmed_type": row.confirmed_type,
                "status": row.status,
                "uploaded_at": row.uploaded_at,
            }
            for row in rows
        ]

    def update_uploaded_document(
        self,
        *,
        session_id: str,
        filename: str,
        confirmed_type: str | None = None,
        status: str | None = None,
    ) -> bool:
        with session_scope() as session:
            record = session.execute(
                select(UploadedDocumentRecord)
                .where(UploadedDocumentRecord.session_id == session_id)
                .where(UploadedDocumentRecord.filename == filename)
                .order_by(UploadedDocumentRecord.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if record is None:
                return False
            if confirmed_type is not None:
                record.confirmed_type = confirmed_type
            if status is not None:
                record.status = status
            return True

    def create_pipeline_run(
        self,
        *,
        run_id: str,
        session_id: str,
        status: str,
        stage: str,
        started_at: str,
    ) -> None:
        with session_scope() as session:
            session.add(
                PipelineRunRecord(
                    run_id=run_id,
                    session_id=session_id,
                    status=status,
                    stage=stage,
                    started_at=started_at,
                    result_json="{}",
                )
            )

    def add_pipeline_run_event(
        self,
        *,
        run_id: str,
        session_id: str,
        stage: str,
        event_type: str,
        created_at: str,
        message: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        with session_scope() as session:
            session.add(
                PipelineRunEventRecord(
                    run_id=run_id,
                    session_id=session_id,
                    stage=stage,
                    event_type=event_type,
                    message=message,
                    metadata_json=json.dumps(metadata or {}),
                    created_at=created_at,
                )
            )

    def list_pipeline_run_events(self, run_id: str) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(
                select(
                    PipelineRunEventRecord.id,
                    PipelineRunEventRecord.run_id,
                    PipelineRunEventRecord.session_id,
                    PipelineRunEventRecord.stage,
                    PipelineRunEventRecord.event_type,
                    PipelineRunEventRecord.message,
                    PipelineRunEventRecord.metadata_json,
                    PipelineRunEventRecord.created_at,
                )
                .where(PipelineRunEventRecord.run_id == run_id)
                .order_by(PipelineRunEventRecord.id.asc())
            ).all()
        return [
            {
                "id": row.id,
                "run_id": row.run_id,
                "session_id": row.session_id,
                "stage": row.stage,
                "event_type": row.event_type,
                "message": row.message,
                "metadata": json.loads(row.metadata_json or "{}"),
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def update_pipeline_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        completed_at: str | None = None,
        error_message: str | None = None,
        result: Dict[str, Any] | None = None,
        chunks_indexed: int | None = None,
        cam_filename: str | None = None,
        cam_file_path: str | None = None,
    ) -> bool:
        with session_scope() as session:
            record = session.execute(
                select(PipelineRunRecord)
                .where(PipelineRunRecord.run_id == run_id)
                .limit(1)
            ).scalar_one_or_none()
            if record is None:
                return False
            if status is not None:
                record.status = status
            if stage is not None:
                record.stage = stage
            if completed_at is not None:
                record.completed_at = completed_at
            if error_message is not None:
                record.error_message = error_message
            if result is not None:
                record.result_json = json.dumps(result)
            if chunks_indexed is not None:
                record.chunks_indexed = chunks_indexed
            if cam_filename is not None:
                record.cam_filename = cam_filename
            if cam_file_path is not None:
                record.cam_file_path = cam_file_path
            return True

    def get_latest_pipeline_run(self, session_id: str) -> Dict[str, Any] | None:
        with session_scope() as session:
            row = session.execute(
                select(
                    PipelineRunRecord.run_id,
                    PipelineRunRecord.session_id,
                    PipelineRunRecord.status,
                    PipelineRunRecord.stage,
                    PipelineRunRecord.started_at,
                    PipelineRunRecord.completed_at,
                    PipelineRunRecord.error_message,
                    PipelineRunRecord.result_json,
                    PipelineRunRecord.chunks_indexed,
                    PipelineRunRecord.cam_filename,
                    PipelineRunRecord.cam_file_path,
                )
                .where(PipelineRunRecord.session_id == session_id)
                .order_by(PipelineRunRecord.started_at.desc())
                .limit(1)
            ).first()
        if row is None:
            return None
        events = self.list_pipeline_run_events(row.run_id)
        return {
            "run_id": row.run_id,
            "session_id": row.session_id,
            "status": row.status,
            "stage": row.stage,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
            "error_message": row.error_message,
            "result": json.loads(row.result_json or "{}"),
            "chunks_indexed": row.chunks_indexed,
            "cam_filename": row.cam_filename,
            "cam_file_path": row.cam_file_path,
            "events": events,
        }

    def get_pipeline_session_details(self, session_id: str) -> Dict[str, Any] | None:
        session_payload = self.get_document_session(session_id)
        if session_payload is None:
            return None
        return {
            **session_payload,
            "documents": self.list_uploaded_documents(session_id),
            "latest_run": self.get_latest_pipeline_run(session_id),
        }

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
        narrative: str | None = None,
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
                    narrative=narrative,
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
                    ScoreAssessmentRecord.narrative,
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
                "narrative": row.narrative,
            }
            for row in rows
        ]

    def update_assessment_narrative(self, *, gstin: str, created_at: str, narrative: str | None) -> bool:
        with session_scope() as session:
            record = session.execute(
                select(ScoreAssessmentRecord)
                .where(ScoreAssessmentRecord.gstin == gstin)
                .where(ScoreAssessmentRecord.created_at == created_at)
                .limit(1)
            ).scalar_one_or_none()
            if record is None:
                return False
            record.narrative = narrative
            return True

    def get_assessment_count(self, gstin: str) -> int:
        with session_scope() as session:
            stmt = select(func.count()).select_from(ScoreAssessmentRecord).where(
                ScoreAssessmentRecord.gstin == gstin
            )
            count = session.scalar(stmt)
        return int(count or 0)

<<<<<<< HEAD
=======
    def count_assessments(self) -> int:
        with session_scope() as session:
            count = session.scalar(select(func.count()).select_from(ScoreAssessmentRecord))
        return int(count or 0)

    def get_latest_assessment_details(self, gstin: str) -> Dict[str, Any] | None:
        with session_scope() as session:
            row = session.execute(
                select(
                    ScoreAssessmentRecord.gstin,
                    ScoreAssessmentRecord.company_name,
                    ScoreAssessmentRecord.credit_score,
                    ScoreAssessmentRecord.risk_band,
                    ScoreAssessmentRecord.fraud_risk,
                    ScoreAssessmentRecord.model_version,
                    ScoreAssessmentRecord.industry_code,
                    ScoreAssessmentRecord.months_active,
                    ScoreAssessmentRecord.scenario,
                    ScoreAssessmentRecord.data_sparse,
                    ScoreAssessmentRecord.freshness_timestamp,
                    ScoreAssessmentRecord.created_at,
                    ScoreAssessmentRecord.top_reasons_json,
                    ScoreAssessmentRecord.recommendation_json,
                    ScoreAssessmentRecord.narrative,
                )
                .where(ScoreAssessmentRecord.gstin == gstin)
                .order_by(ScoreAssessmentRecord.created_at.desc())
                .limit(1)
            ).first()
        if row is None:
            return None
        return {
            "gstin": row.gstin,
            "company_name": row.company_name,
            "credit_score": row.credit_score,
            "risk_band": row.risk_band,
            "fraud_risk": row.fraud_risk,
            "model_version": row.model_version,
            "industry_code": row.industry_code,
            "months_active": row.months_active,
            "scenario": row.scenario,
            "data_sparse": row.data_sparse,
            "freshness_timestamp": row.freshness_timestamp,
            "created_at": row.created_at,
            "top_reasons": json.loads(row.top_reasons_json),
            "recommendation": json.loads(row.recommendation_json),
            "narrative": row.narrative,
        }

    def get_latest_fraud_alert(self, gstin: str) -> Dict[str, Any] | None:
        with session_scope() as session:
            row = session.execute(
                select(
                    FraudAlertRecord.gstin,
                    FraudAlertRecord.company_name,
                    FraudAlertRecord.circular_risk,
                    FraudAlertRecord.risk_score,
                    FraudAlertRecord.cycle_count,
                    FraudAlertRecord.linked_msme_count,
                    FraudAlertRecord.total_volume,
                    FraudAlertRecord.created_at,
                    FraudAlertRecord.alert_payload_json,
                )
                .where(FraudAlertRecord.gstin == gstin)
                .order_by(FraudAlertRecord.created_at.desc())
                .limit(1)
            ).first()
        if row is None:
            return None
        payload = json.loads(row.alert_payload_json)
        payload.setdefault("gstin", row.gstin)
        payload.setdefault("company_name", row.company_name)
        payload.setdefault("circular_risk", row.circular_risk)
        payload.setdefault("risk_score", row.risk_score)
        payload.setdefault("cycle_count", row.cycle_count)
        payload.setdefault("linked_msme_count", row.linked_msme_count)
        payload.setdefault("total_volume", row.total_volume)
        payload.setdefault("created_at", row.created_at)
        return payload

>>>>>>> 05df2af (Harden RAG workflow and ship corporate CAM route)
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

<<<<<<< HEAD
=======
    def get_latest_loan_outcomes_by_gstins(self, gstins: List[str]) -> Dict[str, Dict[str, Any]]:
        normalized = [gstin for gstin in gstins if gstin]
        if not normalized:
            return {}

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
                )
                .where(LoanOutcomeRecord.gstin.in_(normalized))
                .order_by(LoanOutcomeRecord.gstin.asc(), LoanOutcomeRecord.recorded_at.desc())
            ).all()

        latest_by_gstin: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if row.gstin in latest_by_gstin:
                continue
            latest_by_gstin[row.gstin] = {
                "gstin": row.gstin,
                "company_name": row.company_name,
                "repaid": row.repaid,
                "loan_amount": row.loan_amount,
                "tenure_months": row.tenure_months,
                "recorded_at": row.recorded_at,
                "source_model_version": row.source_model_version,
                "feature_snapshot": json.loads(row.feature_snapshot_json),
            }
        return latest_by_gstin

    def create_chat_session(
        self,
        *,
        session_id: str,
        gstin: str,
        created_at: str,
        last_active_at: str,
        expires_at: str,
    ) -> None:
        with session_scope() as session:
            session.add(
                ChatSessionRecord(
                    session_id=session_id,
                    gstin=gstin,
                    created_at=created_at,
                    last_active_at=last_active_at,
                    expires_at=expires_at,
                )
            )

    def get_chat_session(self, session_id: str) -> Dict[str, Any] | None:
        with session_scope() as session:
            row = session.execute(
                select(
                    ChatSessionRecord.session_id,
                    ChatSessionRecord.gstin,
                    ChatSessionRecord.created_at,
                    ChatSessionRecord.last_active_at,
                    ChatSessionRecord.expires_at,
                )
                .where(ChatSessionRecord.session_id == session_id)
                .limit(1)
            ).first()
        if row is None:
            return None
        return {
            "session_id": row.session_id,
            "gstin": row.gstin,
            "created_at": row.created_at,
            "last_active_at": row.last_active_at,
            "expires_at": row.expires_at,
        }

    def touch_chat_session(self, *, session_id: str, last_active_at: str, expires_at: str) -> bool:
        with session_scope() as session:
            record = session.execute(
                select(ChatSessionRecord)
                .where(ChatSessionRecord.session_id == session_id)
                .limit(1)
            ).scalar_one_or_none()
            if record is None:
                return False
            record.last_active_at = last_active_at
            record.expires_at = expires_at
            return True

    def append_chat_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        sources: List[Dict[str, Any]] | None,
        created_at: str,
    ) -> None:
        with session_scope() as session:
            session.add(
                ChatMessageRecord(
                    session_id=session_id,
                    role=role,
                    content=content,
                    sources_json=json.dumps(sources or []),
                    created_at=created_at,
                )
            )

    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(
                select(
                    ChatMessageRecord.role,
                    ChatMessageRecord.content,
                    ChatMessageRecord.sources_json,
                    ChatMessageRecord.created_at,
                )
                .where(ChatMessageRecord.session_id == session_id)
                .order_by(ChatMessageRecord.created_at.asc(), ChatMessageRecord.id.asc())
            ).all()
        return [
            {
                "role": row.role,
                "content": row.content,
                "sources": json.loads(row.sources_json),
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def cleanup_expired_chat_sessions(self, *, now_iso: str) -> int:
        with session_scope() as session:
            expired_ids = session.execute(
                select(ChatSessionRecord.session_id).where(ChatSessionRecord.expires_at < now_iso)
            ).scalars().all()
            if not expired_ids:
                return 0
            session.query(ChatMessageRecord).filter(ChatMessageRecord.session_id.in_(expired_ids)).delete(
                synchronize_session=False
            )
            session.query(ChatSessionRecord).filter(ChatSessionRecord.session_id.in_(expired_ids)).delete(
                synchronize_session=False
            )
            return len(expired_ids)

    def replace_apriori_rules(self, rules: List[Dict[str, Any]], *, created_at: str) -> None:
        with session_scope() as session:
            session.query(AprioriRuleRecord).filter(AprioriRuleRecord.is_active.is_(True)).update(
                {"is_active": False},
                synchronize_session=False,
            )
            for rule in rules:
                existing = session.execute(
                    select(AprioriRuleRecord)
                    .where(AprioriRuleRecord.id == rule["rule_id"])
                    .limit(1)
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        AprioriRuleRecord(
                            id=rule["rule_id"],
                            antecedents_json=json.dumps(rule["antecedents"]),
                            consequent=rule["consequent"],
                            support=rule["support"],
                            confidence=rule["confidence"],
                            lift=rule["lift"],
                            explanation=rule["explanation"],
                            created_at=created_at,
                            is_active=True,
                        )
                    )
                else:
                    existing.antecedents_json = json.dumps(rule["antecedents"])
                    existing.consequent = rule["consequent"]
                    existing.support = rule["support"]
                    existing.confidence = rule["confidence"]
                    existing.lift = rule["lift"]
                    existing.explanation = rule["explanation"]
                    existing.created_at = created_at
                    existing.is_active = True

    def get_active_apriori_rules(self) -> List[Dict[str, Any]]:
        with session_scope() as session:
            rows = session.execute(
                select(
                    AprioriRuleRecord.id,
                    AprioriRuleRecord.antecedents_json,
                    AprioriRuleRecord.consequent,
                    AprioriRuleRecord.support,
                    AprioriRuleRecord.confidence,
                    AprioriRuleRecord.lift,
                    AprioriRuleRecord.explanation,
                    AprioriRuleRecord.created_at,
                )
                .where(AprioriRuleRecord.is_active.is_(True))
                .order_by(
                    AprioriRuleRecord.confidence.desc(),
                    AprioriRuleRecord.lift.desc(),
                    AprioriRuleRecord.support.desc(),
                )
            ).all()
        return [
            {
                "rule_id": row.id,
                "antecedents": json.loads(row.antecedents_json),
                "consequent": row.consequent,
                "support": row.support,
                "confidence": row.confidence,
                "lift": row.lift,
                "explanation": row.explanation,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def get_latest_apriori_rule_created_at(self) -> str | None:
        with session_scope() as session:
            value = session.execute(
                select(func.max(AprioriRuleRecord.created_at)).where(AprioriRuleRecord.is_active.is_(True))
            ).scalar()
        return value

>>>>>>> 05df2af (Harden RAG workflow and ship corporate CAM route)
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
            chat_sessions = session.scalar(select(func.count()).select_from(ChatSessionRecord)) or 0
            chat_messages = session.scalar(select(func.count()).select_from(ChatMessageRecord)) or 0
            apriori_rules = session.scalar(
                select(func.count()).select_from(AprioriRuleRecord).where(AprioriRuleRecord.is_active.is_(True))
            ) or 0

        return {
            "database_url": safe_url,
            "database_path": url.database if safe_url.startswith("sqlite") else None,
            "database_backend": url.get_backend_name(),
            "score_assessments": int(assessments),
            "fraud_alerts": int(alerts),
            "analyst_reviews": int(reviews),
            "loan_outcomes": int(outcomes),
            "model_versions": int(versions),
            "chat_sessions": int(chat_sessions),
            "chat_messages": int(chat_messages),
            "active_apriori_rules": int(apriori_rules),
        }


_storage: ScoreStorage | None = None


def get_storage() -> ScoreStorage:
    global _storage
    if _storage is None:
        _storage = ScoreStorage()
    return _storage
