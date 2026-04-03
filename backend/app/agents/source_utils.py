from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def enrich_agent_result(
    payload: Dict[str, Any],
    *,
    source_name: str,
    source_status: str,
    source_url: str | None = None,
    confidence: float | None = None,
    error_message: str | None = None,
    raw_payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    enriched = dict(payload)
    enriched["source_name"] = source_name
    enriched["source_status"] = source_status
    enriched["source_url"] = source_url
    enriched["retrieved_at"] = enriched.get("retrieved_at") or utc_now_iso()
    enriched["confidence"] = confidence
    enriched["error_message"] = error_message
    if raw_payload is not None:
        enriched["raw_payload"] = raw_payload
    return enriched
