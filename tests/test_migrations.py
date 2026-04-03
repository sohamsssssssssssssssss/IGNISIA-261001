import importlib.util
from pathlib import Path

import pytest


HAS_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None
HAS_ALEMBIC = importlib.util.find_spec("alembic") is not None


pytestmark = pytest.mark.skipif(
    not (HAS_SQLALCHEMY and HAS_ALEMBIC),
    reason="sqlalchemy and alembic are required for migration tests",
)

if HAS_SQLALCHEMY and HAS_ALEMBIC:
    from sqlalchemy import create_engine, inspect

    from app.core.database import reset_database_runtime
    from app.core.settings import get_settings
    from app.core.migrations import run_database_migrations


def test_run_database_migrations_applies_latest_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "migration-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))

    get_settings.cache_clear()
    reset_database_runtime()

    run_database_migrations()

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "document_sessions" in tables
    assert "pipeline_runs" in tables
    assert "pipeline_run_events" in tables

    get_settings.cache_clear()
    reset_database_runtime()
