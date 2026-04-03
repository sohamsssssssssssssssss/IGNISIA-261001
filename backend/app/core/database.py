"""
SQLAlchemy database configuration shared by the API and migration tooling.
Supports SQLite for local/demo workflows and Postgres for deployed environments.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings


class Base(DeclarativeBase):
    """Base declarative model class for persistence entities."""


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
        FraudAlertRecord,
        LoanOutcomeRecord,
        ModelVersionRecord,
        MonitoredGSTINRecord,
        PipelineDataRecord,
        ScoreAssessmentRecord,
    )

    _ = (
        ScoreAssessmentRecord,
        FraudAlertRecord,
        AnalystReviewRecord,
        PipelineDataRecord,
        MonitoredGSTINRecord,
        LoanOutcomeRecord,
        ModelVersionRecord,
    )
    Base.metadata.create_all(bind=get_engine())


def reset_database_runtime() -> None:
    """Clear cached engine/session objects for tests that patch env vars."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
