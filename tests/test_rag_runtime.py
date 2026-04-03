from app.core.rag_runtime import get_rag_capabilities, reset_rag_capabilities


def test_rag_capabilities_handle_missing_parent_module(monkeypatch):
    monkeypatch.delenv("ENABLE_RAG", raising=False)

    import app.core.rag_runtime as rag_runtime

    def _fake_find_spec(name):
        if name == "llama_index":
            return None
        if name in {"llama_index.core", "llama_index.vector_stores.chroma"}:
            raise ModuleNotFoundError("No module named 'llama_index'")
        return object()

    monkeypatch.setattr(rag_runtime, "get_chroma_client", lambda: object())
    monkeypatch.setattr(rag_runtime.importlib.util, "find_spec", _fake_find_spec)

    reset_rag_capabilities()
    capabilities = get_rag_capabilities()

    assert capabilities["base_pipeline_ready"] is False
    assert capabilities["execution_mode"] == "disabled"


def test_rag_capabilities_support_reduced_mode(monkeypatch):
    monkeypatch.delenv("ENABLE_RAG", raising=False)
    monkeypatch.delenv("ENABLE_WEB_INTEL", raising=False)
    monkeypatch.delenv("ENABLE_LOCAL_GENERATION", raising=False)

    import app.core.rag_runtime as rag_runtime

    monkeypatch.setattr(rag_runtime, "get_chroma_client", lambda: object())
    monkeypatch.setattr(
        rag_runtime,
        "_has_module",
        lambda name: name in {"llama_index", "llama_index.core", "llama_index.vector_stores.chroma"},
    )

    reset_rag_capabilities()
    capabilities = get_rag_capabilities()

    assert capabilities["rag_enabled"] is True
    assert capabilities["modes"]["document_pipeline"] is True
    assert capabilities["modes"]["document_pipeline_with_generation"] is False
    assert capabilities["modes"]["document_pipeline_with_web_intel"] is False
    assert capabilities["execution_mode"] == "reduced"
    assert "local_generation_unavailable" in capabilities["degradations"]
    assert "web_intel_unavailable" in capabilities["degradations"]


def test_rag_capabilities_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_RAG", "false")

    import app.core.rag_runtime as rag_runtime

    monkeypatch.setattr(rag_runtime, "get_chroma_client", lambda: object())
    monkeypatch.setattr(rag_runtime, "_has_module", lambda name: True)

    reset_rag_capabilities()
    capabilities = get_rag_capabilities()

    assert capabilities["rag_enabled"] is False
    assert capabilities["modes"]["document_pipeline"] is False
    assert capabilities["modes"]["document_pipeline_with_generation"] is False
    assert capabilities["modes"]["document_pipeline_with_web_intel"] is False
    assert capabilities["execution_mode"] == "disabled"
    assert capabilities["degradations"] == []
