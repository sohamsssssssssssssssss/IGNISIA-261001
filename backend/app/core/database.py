"""
SQLAlchemy database configuration shared by the API and migration tooling.
Supports SQLite for local/demo workflows and Postgres for deployed environments.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings


class Base(DeclarativeBase):
    """Base declarative model class for persistence entities."""


SQLITE_COMPATIBILITY_COLUMNS = {
    "score_assessments": {
        "industry_code": "VARCHAR(32)",
        "months_active": "FLOAT NOT NULL DEFAULT 0",
        "narrative": "TEXT",
        "concept_scores_json": "TEXT",
        "shap_top_factors_json": "TEXT",
        "llm_narrative": "TEXT",
        "swot_json": "TEXT",
        "triangulation_json": "TEXT",
    },
    "document_sessions": {
        "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        "last_error": "TEXT",
        "cam_filename": "VARCHAR(255)",
        "cam_file_path": "TEXT",
    },
    "pipeline_runs": {
        "result_json": "TEXT NOT NULL DEFAULT '{}'",
        "chunks_indexed": "INTEGER NOT NULL DEFAULT 0",
        "cam_filename": "VARCHAR(255)",
        "cam_file_path": "TEXT",
    },
    "pipeline_run_events": {
        "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
    },
    "apriori_rules": {
        "record_count": "INTEGER NOT NULL DEFAULT 0",
        "generated_at": "VARCHAR(64)",
    },
}


def _build_engine(database_url: str) -> Engine:
    engine_kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **engine_kwargs)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().database_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )
    return _session_factory


def _ensure_sqlite_backward_compatible_columns(engine: Engine) -> None:
    """
    Older local/demo SQLite files may predate newer persistence columns.
    `create_all()` will create missing tables, but it will not add missing
    columns to existing tables, so we heal those columns in place here.
    """
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, columns in SQLITE_COMPATIBILITY_COLUMNS.items():
            if table_name not in existing_tables:
                continue

            existing_columns = {
                column["name"]
                for column in inspector.get_columns(table_name)
            }

            for column_name, column_sql in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(
                    text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_sql}')
                )

        if "apriori_rules" in existing_tables:
            apriori_columns = {
                column["name"]
                for column in inspect(engine).get_columns("apriori_rules")
            }
            if "generated_at" in apriori_columns and "created_at" in apriori_columns:
                connection.execute(
                    text(
                        "UPDATE apriori_rules "
                        "SET generated_at = COALESCE(generated_at, created_at)"
                    )
                )


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database() -> None:
    """
    Create tables for local/test environments.
    In production, Alembic migrations should be the primary schema manager.
    """
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

    _ = (
        ScoreAssessmentRecord,
        FraudAlertRecord,
        AnalystReviewRecord,
        ChatSessionRecord,
        ChatMessageRecord,
        DocumentSessionRecord,
        UploadedDocumentRecord,
        PipelineRunRecord,
        PipelineRunEventRecord,
        AprioriRuleRecord,
        PipelineDataRecord,
        MonitoredGSTINRecord,
        LoanOutcomeRecord,
        ModelVersionRecord,
    )
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_backward_compatible_columns(engine)


def reset_database_runtime() -> None:
    """Clear cached engine/session objects for tests that patch env vars."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
