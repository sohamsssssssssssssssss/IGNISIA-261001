import importlib.util
import json
import importlib
import sys
import types

import pytest


HAS_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None


pytestmark = pytest.mark.skipif(
    not HAS_SQLALCHEMY,
    reason="sqlalchemy is not installed in this environment",
)

if HAS_SQLALCHEMY:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core import storage as storage_module
    from app.core.database import reset_database_runtime
    from app.core.rag_runtime import reset_rag_capabilities
    from app.core.settings import get_settings


@pytest.fixture()
def upload_module(monkeypatch):
    parser_specs = {
        "app.parsers.alm_parser": ("parse_alm", {"stub": "alm"}),
        "app.parsers.borrowing_profile_parser": (
            "parse_borrowing_profile",
            {"stub": "borrowing_profile"},
        ),
        "app.parsers.portfolio_parser": ("parse_portfolio_cuts", {"stub": "portfolio_cuts"}),
        "app.parsers.shareholding_parser": ("parse_shareholding", {"stub": "shareholding"}),
    }
    for module_name, (function_name, return_value) in parser_specs.items():
        fake_module = types.ModuleType(module_name)
        setattr(fake_module, function_name, lambda *_args, value=return_value, **_kwargs: value)
        monkeypatch.setitem(sys.modules, module_name, fake_module)

    sys.modules.pop("app.api.upload_endpoint", None)
    return importlib.import_module("app.api.upload_endpoint")


@pytest.fixture()
def client(tmp_path, monkeypatch, upload_module):
    db_path = tmp_path / "upload-pipeline.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("REQUIRE_AUTH", "false")

    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()
    reset_rag_capabilities()

    app = FastAPI()
    app.include_router(upload_module.router)

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()
    reset_rag_capabilities()


def _upload_single_document(client: "TestClient") -> dict:
    response = client.post(
        "/api/upload",
        files=[
            (
                "files",
                (
                    "annual_report.txt",
                    b"annual report revenue cash flow profit and loss",
                    "text/plain",
                ),
            )
        ],
    )
    assert response.status_code == 200
    return response.json()


def _confirm_single_document(client: "TestClient", session_id: str) -> dict:
    response = client.post(
        "/api/upload/confirm",
        data={
            "session_id": session_id,
            "confirmations": json.dumps(
                [
                    {
                        "filename": "annual_report.txt",
                        "predicted_type": "ANNUAL_REPORT",
                        "confirmed_type": "ANNUAL_REPORT",
                    }
                ]
            ),
        },
    )
    assert response.status_code == 200
    return response.json()


def test_upload_confirm_and_status_persist_session_state(client):
    upload_payload = _upload_single_document(client)
    session_id = upload_payload["session_id"]

    assert upload_payload["workflow_status"] == "uploaded"
    assert len(upload_payload["classifications"]) == 1
    assert upload_payload["classifications"][0]["predicted_type"] == "ANNUAL_REPORT"

    confirm_response = _confirm_single_document(client, session_id)
    assert confirm_response["workflow_status"] == "classified"

    status_response = client.get(f"/api/pipeline/{session_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()

    assert status_payload["session_id"] == session_id
    assert status_payload["workflow_status"] == "classified"
    assert status_payload["latest_run"] is None
    assert len(status_payload["classifications"]) == 1
    assert status_payload["classifications"][0]["status"] == "APPROVED"
    assert status_payload["rag_capabilities"]["execution_mode"] in {"disabled", "reduced", "full"}


def test_upload_confirm_marks_overridden_classification_as_edited(client):
    upload_payload = _upload_single_document(client)
    session_id = upload_payload["session_id"]

    response = client.post(
        "/api/upload/confirm",
        data={
            "session_id": session_id,
            "confirmations": json.dumps(
                [
                    {
                        "filename": "annual_report.txt",
                        "predicted_type": "ANNUAL_REPORT",
                        "confirmed_type": "BORROWING_PROFILE",
                    }
                ]
            ),
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["workflow_status"] == "classified"
    assert payload["classifications"][0]["confirmed_type"] == "BORROWING_PROFILE"
    assert payload["classifications"][0]["status"] == "EDITED"


def test_pipeline_run_persists_completed_run_in_reduced_mode(client, monkeypatch, upload_module):
    upload_payload = _upload_single_document(client)
    session_id = upload_payload["session_id"]

    _confirm_single_document(client, session_id)

    fake_capabilities = {
        "rag_enabled": True,
        "base_pipeline_ready": True,
        "generation_ready": False,
        "web_intel_ready": False,
        "execution_mode": "reduced",
        "degradations": ["local_generation_unavailable", "web_intel_unavailable"],
        "dependencies": {},
        "modes": {
            "document_pipeline": True,
            "document_pipeline_with_generation": False,
            "document_pipeline_with_web_intel": False,
        },
    }
    monkeypatch.setattr(upload_module, "get_rag_capabilities", lambda: fake_capabilities)

    fake_pipeline_module = types.ModuleType("app.rag.pipeline")

    class FakeRAGPipeline:
        def __init__(self, company_name, promoter_name, industry, gstin, **kwargs):
            self.company_name = company_name

        def run_full(self, **kwargs):
            return types.SimpleNamespace(
                chunks_indexed=4,
                contradiction_report=types.SimpleNamespace(contradictions=[]),
                    web_intel_report=types.SimpleNamespace(
                        status="skipped",
                        skipped_reason="tavily_unavailable",
                        queries_run=[],
                        results_indexed=0,
                        key_findings=["Web intelligence skipped because Tavily is not configured in this runtime."],
                        query_reports=[],
                    ),
                    cam_sections={
                        "swot": {
                            "strengths": ["Stable reported revenue."],
                        "weaknesses": [],
                        "opportunities": [],
                        "threats": [],
                        }
                    },
                    provenance_summary={"session_id": session_id, "pipeline_run_id": "stub-run", "documents": []},
                )

    fake_pipeline_module.RAGPipeline = FakeRAGPipeline
    monkeypatch.setitem(sys.modules, "app.rag.pipeline", fake_pipeline_module)

    def _write_cam_docx(cam_data, cam_path):
        with open(cam_path, "wb") as handle:
            handle.write(b"fake-docx")

    monkeypatch.setattr(upload_module._cam_gen, "generate_cam_docx", _write_cam_docx)

    run_response = client.post(
        "/api/pipeline/run",
        data={
            "session_id": session_id,
            "company_name": "Acme Manufacturing Pvt Ltd",
            "sector": "Manufacturing",
            "promoter": "A. Kumar",
            "pan": "ABCDE1234F",
            "loan_amount": "2500000",
            "loan_tenure": "24",
            "loan_rate": "11.5%",
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()

    assert run_payload["session_id"] == session_id
    assert run_payload["execution_mode"] == "reduced"
    assert run_payload["web_intel"]["status"] == "skipped"
    assert run_payload["chunks_indexed"] == 4
    assert run_payload["cam_download_url"].startswith("/api/download/CAM_")

    status_response = client.get(f"/api/pipeline/{session_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()

    assert status_payload["workflow_status"] == "completed"
    assert status_payload["cam_download_url"] == run_payload["cam_download_url"]
    assert status_payload["latest_run"]["status"] == "completed"
    assert status_payload["latest_run"]["chunks_indexed"] == 4
    assert status_payload["latest_run"]["result"]["execution_mode"] == "reduced"
    assert [event["stage"] for event in status_payload["latest_run"]["events"]] == [
        "preparing_inputs",
        "preparing_inputs",
        "parsing_documents",
        "rag_execution",
        "cam_generation",
        "completed",
    ]


def test_pipeline_run_returns_503_when_base_pipeline_is_unavailable(client, monkeypatch, upload_module):
    upload_payload = _upload_single_document(client)
    session_id = upload_payload["session_id"]
    _confirm_single_document(client, session_id)

    fake_capabilities = {
        "rag_enabled": True,
        "base_pipeline_ready": False,
        "generation_ready": False,
        "web_intel_ready": False,
        "execution_mode": "disabled",
        "degradations": [],
        "dependencies": {"chromadb_runtime": False},
        "modes": {
            "document_pipeline": False,
            "document_pipeline_with_generation": False,
            "document_pipeline_with_web_intel": False,
        },
    }
    monkeypatch.setattr(upload_module, "get_rag_capabilities", lambda: fake_capabilities)

    run_response = client.post(
        "/api/pipeline/run",
        data={
            "session_id": session_id,
            "company_name": "Acme Manufacturing Pvt Ltd",
            "sector": "Manufacturing",
            "promoter": "A. Kumar",
            "pan": "ABCDE1234F",
        },
    )
    assert run_response.status_code == 503
    assert run_response.json()["detail"]["capabilities"]["execution_mode"] == "disabled"

    status_response = client.get(f"/api/pipeline/{session_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()

    assert status_payload["workflow_status"] == "classified"
    assert status_payload["latest_run"] is None
    assert status_payload["last_error"] is None


def test_pipeline_run_persists_failed_run_state(client, monkeypatch, upload_module):
    upload_payload = _upload_single_document(client)
    session_id = upload_payload["session_id"]
    _confirm_single_document(client, session_id)

    fake_capabilities = {
        "rag_enabled": True,
        "base_pipeline_ready": True,
        "generation_ready": False,
        "web_intel_ready": False,
        "execution_mode": "reduced",
        "degradations": ["local_generation_unavailable", "web_intel_unavailable"],
        "dependencies": {},
        "modes": {
            "document_pipeline": True,
            "document_pipeline_with_generation": False,
            "document_pipeline_with_web_intel": False,
        },
    }
    monkeypatch.setattr(upload_module, "get_rag_capabilities", lambda: fake_capabilities)

    fake_pipeline_module = types.ModuleType("app.rag.pipeline")

    class FailingRAGPipeline:
        def __init__(self, company_name, promoter_name, industry, gstin, **kwargs):
            self.company_name = company_name

        def run_full(self, **kwargs):
            raise RuntimeError("synthetic rag failure")

    fake_pipeline_module.RAGPipeline = FailingRAGPipeline
    monkeypatch.setitem(sys.modules, "app.rag.pipeline", fake_pipeline_module)

    run_response = client.post(
        "/api/pipeline/run",
        data={
            "session_id": session_id,
            "company_name": "Acme Manufacturing Pvt Ltd",
            "sector": "Manufacturing",
            "promoter": "A. Kumar",
            "pan": "ABCDE1234F",
            "loan_amount": "2500000",
            "loan_tenure": "24",
            "loan_rate": "11.5%",
        },
    )
    assert run_response.status_code == 500
    assert run_response.json()["detail"] == "Pipeline execution failed: synthetic rag failure"

    status_response = client.get(f"/api/pipeline/{session_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()

    assert status_payload["workflow_status"] == "failed"
    assert status_payload["last_error"] == "synthetic rag failure"
    assert status_payload["latest_run"]["status"] == "failed"
    assert status_payload["latest_run"]["stage"] == "failed"
    assert status_payload["latest_run"]["error_message"] == "synthetic rag failure"
    assert status_payload["latest_run"]["completed_at"] is not None
    assert status_payload["latest_run"]["events"][-1]["event_type"] == "failed"
    assert status_payload["latest_run"]["events"][-1]["metadata"]["error_message"] == "synthetic rag failure"
