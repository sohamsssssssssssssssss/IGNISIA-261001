import importlib
import importlib.util

import pytest


HAS_SQLALCHEMY = importlib.util.find_spec("sqlalchemy") is not None


pytestmark = pytest.mark.skipif(
    not HAS_SQLALCHEMY,
    reason="sqlalchemy is not installed in this environment",
)

if HAS_SQLALCHEMY:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.settings import get_settings


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()

    import app.api.agent_status_endpoint as agent_status_module

    agent_status_module = importlib.reload(agent_status_module)
    app = FastAPI()
    app.include_router(agent_status_module.router)

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_agent_status_returns_normalized_agent_metadata(client):
    response = client.get("/api/agent-status/CleanTech%20Manufacturing%20Ltd.")
    assert response.status_code == 200

    payload = response.json()
    assert payload["demo_mode"] is True
    agents = payload["agents"]

    assert agents["mca"]["data"]["source_name"] == "mca21"
    assert agents["mca"]["data"]["source_url"] == "https://www.mca.gov.in/"
    assert agents["ecourts"]["data"]["source_name"] == "ecourts"
    assert agents["rbi_watchlist"]["data"]["source_name"] == "rbi_wilful_defaulters"
    assert agents["news"]["data"]["source_name"] == "tavily_news"
    assert agents["news"]["data"]["retrieved_at"]
    assert "confidence" in agents["news"]["data"]


def test_agent_status_marks_news_unavailable_without_tavily_key(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    get_settings.cache_clear()

    import app.api.agent_status_endpoint as agent_status_module

    agent_status_module = importlib.reload(agent_status_module)
    app = FastAPI()
    app.include_router(agent_status_module.router)

    with TestClient(app) as test_client:
        response = test_client.get("/api/agent-status/CleanTech%20Manufacturing%20Ltd.")

    assert response.status_code == 200
    payload = response.json()
    news = payload["agents"]["news"]["data"]

    assert news["source_status"] == "unavailable"
    assert news["error_message"] == "TAVILY_API_KEY is not configured"
    assert news["source_name"] == "tavily_news"

    get_settings.cache_clear()
