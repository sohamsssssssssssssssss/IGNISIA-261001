"""
Runtime capability helpers for the optional RAG and web-intel workflow.
"""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from typing import Any, Dict

from .chroma_client import get_chroma_client


def _env_enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


@lru_cache(maxsize=1)
def get_rag_capabilities() -> Dict[str, Any]:
    rag_enabled = _env_enabled("ENABLE_RAG", default=True)
    web_intel_enabled = rag_enabled and _env_enabled("ENABLE_WEB_INTEL", default=True)
    local_generation_enabled = rag_enabled and _env_enabled("ENABLE_LOCAL_GENERATION", default=True)

    chroma_available = get_chroma_client() is not None
    llama_index_available = (
        _has_module("llama_index")
        or (_has_module("llama_index.core") and _has_module("llama_index.vector_stores.chroma"))
    )
    ollama_package_available = _has_module("ollama")
    tavily_package_available = _has_module("tavily")

    base_pipeline_ready = rag_enabled and chroma_available and llama_index_available
    generation_ready = local_generation_enabled and ollama_package_available
    web_intel_ready = web_intel_enabled and tavily_package_available and bool(os.getenv("TAVILY_API_KEY"))
    degradations = []
    if base_pipeline_ready and not generation_ready:
        degradations.append("local_generation_unavailable")
    if base_pipeline_ready and not web_intel_ready:
        degradations.append("web_intel_unavailable")
    execution_mode = (
        "disabled"
        if not base_pipeline_ready
        else "full"
        if generation_ready and web_intel_ready
        else "reduced"
    )

    return {
        "rag_enabled": rag_enabled,
        "base_pipeline_ready": base_pipeline_ready,
        "generation_ready": generation_ready,
        "web_intel_ready": web_intel_ready,
        "execution_mode": execution_mode,
        "degradations": degradations,
        "dependencies": {
            "chromadb_runtime": chroma_available,
            "llama_index": llama_index_available,
            "ollama_package": ollama_package_available,
            "tavily_package": tavily_package_available,
            "tavily_api_key_configured": bool(os.getenv("TAVILY_API_KEY")),
            "anthropic_api_key_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            "groq_api_key_configured": bool(os.getenv("GROQ_API_KEY")),
        },
        "modes": {
            "document_pipeline": base_pipeline_ready,
            "document_pipeline_with_generation": base_pipeline_ready and generation_ready,
            "document_pipeline_with_web_intel": base_pipeline_ready and web_intel_ready,
        },
    }


def reset_rag_capabilities() -> None:
    get_rag_capabilities.cache_clear()
