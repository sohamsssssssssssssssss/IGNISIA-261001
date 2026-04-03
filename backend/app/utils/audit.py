from __future__ import annotations

from datetime import datetime
from typing import Dict, List


class AuditTrail:
    def __init__(self) -> None:
        self._entries: List[Dict[str, object]] = []
        self._start_time = datetime.now()

    def log(self, message: str) -> None:
        now = datetime.now()
        self._entries.append(
            {
                "timestamp": now.strftime("%H:%M:%S.%f")[:-3],
                "message": message,
                "elapsed_ms": round((now - self._start_time).total_seconds() * 1000, 1),
            }
        )

    def to_list(self) -> List[Dict[str, object]]:
        return self._entries
