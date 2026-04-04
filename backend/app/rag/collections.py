"""
Shared collection handles for the corporate RAG pipeline.

When Chroma is unavailable, these resolve to `None` and the indexer layer falls
back to an in-memory implementation.
"""

from __future__ import annotations

from ..core.chroma_client import get_chroma_collection


BORROWER_COLLECTION = get_chroma_collection("borrower_provided")
GOVT_COLLECTION = get_chroma_collection("government_authoritative")
EXTERNAL_COLLECTION = get_chroma_collection("external_unverified")
