"""
ORM persistence models for durable score history, fraud alerts, and analyst audit logs.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ScoreAssessmentRecord(Base):
    __tablename__ = "score_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gstin: Mapped[str] = mapped_column(String(32), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit_score: Mapped[int] = mapped_column(Integer)
    risk_band: Mapped[str] = mapped_column(String(64))
    fraud_risk: Mapped[str] = mapped_column(String(32))
    model_version: Mapped[str] = mapped_column(String(128))
    industry_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    months_active: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scenario: Mapped[str] = mapped_column(String(32))
    data_sparse: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    freshness_timestamp: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(32), default="api", nullable=False)
    top_reasons_json: Mapped[str] = mapped_column(Text)
    recommendation_json: Mapped[str] = mapped_column(Text)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)


class FraudAlertRecord(Base):
    __tablename__ = "fraud_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gstin: Mapped[str] = mapped_column(String(32), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    circular_risk: Mapped[str] = mapped_column(String(32))
    risk_score: Mapped[int] = mapped_column(Integer)
    cycle_count: Mapped[int] = mapped_column(Integer)
    linked_msme_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_volume: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    alert_payload_json: Mapped[str] = mapped_column(Text)


class PipelineDataRecord(Base):
    """
    Stores the latest ingested pipeline output for each (GSTIN, pipeline_type).
    Updated by background workers on a schedule — the scoring endpoint reads
    from here instead of generating data on the fly.
    """
    __tablename__ = "pipeline_data"
    __table_args__ = (
        UniqueConstraint("gstin", "pipeline_type", name="uq_pipeline_data_gstin_pipeline_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gstin: Mapped[str] = mapped_column(String(32), index=True)
    pipeline_type: Mapped[str] = mapped_column(String(32))  # gst_velocity | upi_cadence | eway_bill
    epoch: Mapped[int] = mapped_column(Integer, default=0)  # increments each worker run
    ingested_at: Mapped[str] = mapped_column(String(64), index=True)
    data_json: Mapped[str] = mapped_column(Text)


class MonitoredGSTINRecord(Base):
    """
    Tracks which GSTINs the background workers should generate data for.
    Demo GSTINs are seeded on startup; new ones are added when first queried.
    """
    __tablename__ = "monitored_gstins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gstin: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    added_at: Mapped[str] = mapped_column(String(64))


class LoanOutcomeRecord(Base):
    __tablename__ = "loan_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gstin: Mapped[str] = mapped_column(String(32), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    repaid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    loan_amount: Mapped[float] = mapped_column(Float, nullable=False)
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(64), index=True)
    source_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    feature_snapshot_json: Mapped[str] = mapped_column(Text)


class ModelVersionRecord(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(128), index=True)
    trained_at: Mapped[str] = mapped_column(String(64), index=True)
    training_sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    synthetic_sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    real_sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    real_label_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    auc_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    auc_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    feature_schema_version: Mapped[str] = mapped_column(String(128), nullable=False, default="unknown")
    metrics_json: Mapped[str] = mapped_column(Text)


class AnalystReviewRecord(Base):
    __tablename__ = "analyst_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    analyst_action: Mapped[str] = mapped_column(String(32))
    original_score: Mapped[float] = mapped_column(Float)
    adjusted_score: Mapped[float] = mapped_column(Float)
    total_adjustment: Mapped[float] = mapped_column(Float)
    original_verdict: Mapped[str] = mapped_column(String(32))
    adjusted_verdict: Mapped[str] = mapped_column(String(32))
    management_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    factory_utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    field_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)


class ChatSessionRecord(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    gstin: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    last_active_at: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[str] = mapped_column(String(64), index=True)


class ChatMessageRecord(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.session_id"), index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String(64), index=True)


class DocumentSessionRecord(Base):
    __tablename__ = "document_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    updated_at: Mapped[str] = mapped_column(String(64), index=True)
    workflow_status: Mapped[str] = mapped_column(String(32), index=True, default="uploaded")
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cam_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cam_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class UploadedDocumentRecord(Base):
    __tablename__ = "uploaded_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("document_sessions.session_id"), index=True)
    filename: Mapped[str] = mapped_column(String(255), index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    predicted_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="PENDING")
    uploaded_at: Mapped[str] = mapped_column(String(64), index=True)


class PipelineRunRecord(Base):
    __tablename__ = "pipeline_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("document_sessions.session_id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[str] = mapped_column(String(64), index=True)
    completed_at: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    chunks_indexed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cam_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cam_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class PipelineRunEventRecord(Base):
    __tablename__ = "pipeline_run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.run_id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("document_sessions.session_id"), index=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), index=True)


class AprioriRuleRecord(Base):
    __tablename__ = "apriori_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    antecedents_json: Mapped[str] = mapped_column(Text, nullable=False)
    consequent: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    support: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    lift: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
