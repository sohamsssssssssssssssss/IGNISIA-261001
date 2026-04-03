"""
Durable chat session store backed by the application database.
Sessions expire after two hours of inactivity.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from typing import Dict, List
from uuid import uuid4

from .storage import get_storage


SESSION_TTL_SECONDS = 2 * 60 * 60


class SessionStore:
    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS, storage=None) -> None:
        self.ttl_seconds = ttl_seconds
        self.storage = storage or get_storage()
        self._lock = Lock()

    def create_session(self, gstin: str) -> str:
        session_id = self._build_session_id()
        now = self._now()
        with self._lock:
            self.storage.cleanup_expired_chat_sessions(now_iso=now["iso"])
            self.storage.create_chat_session(
                session_id=session_id,
                gstin=gstin,
                created_at=now["iso"],
                last_active_at=now["iso"],
                expires_at=now["expires_at"],
            )
        return session_id

    def get_or_create_session(self, gstin: str, session_id: str | None = None) -> str:
        with self._lock:
            now = self._now()
            self.storage.cleanup_expired_chat_sessions(now_iso=now["iso"])
            if session_id:
                entry = self.storage.get_chat_session(session_id)
                if entry is not None and entry["gstin"] == gstin:
                    self.storage.touch_chat_session(
                        session_id=session_id,
                        last_active_at=now["iso"],
                        expires_at=now["expires_at"],
                    )
                    return session_id
        return self.create_session(gstin)

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        with self._lock:
            now = self._now()
            self.storage.cleanup_expired_chat_sessions(now_iso=now["iso"])
            entry = self.storage.get_chat_session(session_id)
            if entry is None:
                return []
            self.storage.touch_chat_session(
                session_id=session_id,
                last_active_at=now["iso"],
                expires_at=now["expires_at"],
            )
            history = self.storage.get_chat_history(session_id)
        return [{"role": item["role"], "content": item["content"]} for item in history]

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: List[Dict[str, str]] | None = None,
    ) -> None:
        with self._lock:
            now = self._now()
            self.storage.cleanup_expired_chat_sessions(now_iso=now["iso"])
            entry = self.storage.get_chat_session(session_id)
            if entry is None:
                raise KeyError(f"Unknown session_id: {session_id}")
            self.storage.touch_chat_session(
                session_id=session_id,
                last_active_at=now["iso"],
                expires_at=now["expires_at"],
            )
            self.storage.append_chat_message(
                session_id=session_id,
                role=role,
                content=content,
                sources=sources,
                created_at=now["iso"],
            )

    def cleanup_expired(self) -> int:
        with self._lock:
            now = self._now()
            return self.storage.cleanup_expired_chat_sessions(now_iso=now["iso"])

    def has_session(self, session_id: str) -> bool:
        with self._lock:
            now = self._now()
            self.storage.cleanup_expired_chat_sessions(now_iso=now["iso"])
            return self.storage.get_chat_session(session_id) is not None

    def _now(self) -> Dict[str, str]:
        timestamp = datetime.now(timezone.utc)
        expires_at = timestamp + timedelta(seconds=self.ttl_seconds)
        return {
            "iso": timestamp.isoformat().replace("+00:00", "Z"),
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        }

    def _build_session_id(self) -> str:
        return str(uuid4())


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    return SessionStore()
