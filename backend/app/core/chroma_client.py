"""
Shared Chroma client and collection registry.
Keeps all vector collections on one persistent local database.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from .settings import get_settings

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except Exception:  # pragma: no cover - optional dependency/runtime compatibility varies by env
    chromadb = None
    ChromaSettings = None


logger = logging.getLogger("intellicredit.chroma")


COLLECTION_SPECS: Dict[str, Dict[str, Any]] = {
    "score_history": {
        "description": "Embedded score payloads for historical MSME similarity search",
        "domain": "scoring",
        "hnsw:space": "cosine",
    },
    "rules": {
        "description": "Apriori rules, RBI guidance, and NIC industry risk profiles",
        "domain": "reference",
        "hnsw:space": "cosine",
    },
    "fraud_patterns": {
        "description": "Embedded historical fraud-ring detections and graph patterns",
        "domain": "fraud",
        "hnsw:space": "cosine",
    },
    "borrower_provided": {
        "description": "Borrower-uploaded documents",
        "trust_level": "1.0",
        "domain": "rag",
    },
    "government_authoritative": {
        "description": "Government and regulator sources such as RBI and eCourts",
        "trust_level": "0.9",
        "domain": "rag",
    },
    "external_unverified": {
        "description": "External web and news sources",
        "trust_level": "0.6",
        "domain": "rag",
    },
}


_client = None
_collections: Dict[str, Any] = {}


def get_chroma_client():
    global _client
    if _client is not None:
        return _client
    if chromadb is None or ChromaSettings is None:
        return None

    settings = get_settings()
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    try:
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    except Exception as exc:  # pragma: no cover - runtime compatibility varies by env
        logger.warning("Chroma client unavailable; vector features disabled: %s", exc)
        return None
    return _client


def get_chroma_collection(name: str):
    if name not in COLLECTION_SPECS:
        raise ValueError(f"Unsupported Chroma collection: {name}")
    if name in _collections:
        return _collections[name]

    client = get_chroma_client()
    if client is None:
        return None

    spec = COLLECTION_SPECS[name]
    try:
        collection = client.get_or_create_collection(
            name=name,
            metadata={k: v for k, v in spec.items()},
        )
    except Exception as exc:  # pragma: no cover - runtime compatibility varies by env
        logger.warning("Chroma collection %s unavailable; vector features disabled: %s", name, exc)
        return None
    _collections[name] = collection
    return collection


def ensure_chroma_collections() -> Dict[str, Any]:
    return {name: get_chroma_collection(name) for name in COLLECTION_SPECS}


def reset_chroma_client() -> None:
    global _client
    _client = None
    _collections.clear()
