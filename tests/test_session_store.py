import time
import importlib.util
from uuid import UUID

import pytest


HAS_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None


pytestmark = pytest.mark.skipif(
    not HAS_SQLALCHEMY,
    reason="sqlalchemy is not installed in this environment",
)

if HAS_SQLALCHEMY:
    from app.core import storage as storage_module
    from app.core.database import reset_database_runtime
    from app.core.settings import get_settings
    from app.core.session_store import SessionStore


def test_session_store_creates_and_appends_messages(tmp_path, monkeypatch):
    db_path = tmp_path / "session-store.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()

    store = SessionStore(ttl_seconds=7200)
    session_id = store.create_session("29CLEAN5678B1Z2")

    assert str(UUID(session_id)) == session_id
    assert store.has_session(session_id) is True

    store.append_message(session_id, "user", "Should I approve this borrower?")
    store.append_message(session_id, "assistant", "The score is 742 with low fraud risk.")
    history = store.get_history(session_id)

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["content"] == "The score is 742 with low fraud risk."


def test_session_store_expires_inactive_sessions(tmp_path, monkeypatch):
    db_path = tmp_path / "session-expiry.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()

    store = SessionStore(ttl_seconds=1)
    session_id = store.create_session("29CLEAN5678B1Z2")

    time.sleep(1.1)
    expired = store.cleanup_expired()

    assert expired == 1
    assert store.has_session(session_id) is False
