import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.database import reset_database_runtime
from app.core.entity_graph import reset_entity_graph_service
from app.core.settings import get_settings
from app.core import storage as storage_module
from app.core.storage import get_storage
from app.core.xgboost_model import get_scorer, recommend_loan, reset_scorer
from app.services.counterfactual_engine import CounterfactualEngine
from app.services.lender_matcher import LenderMatcher
from app.services.trajectory_projector import TrajectoryProjector
from app.services.feature_engineering import POPULATION_DEFAULTS, _confidence_weight


def _reset_service_caches():
    from app.core.chroma_client import reset_chroma_client
    from app.core.session_store import get_session_store
    from app.services.embedding_service import get_embedding_service
    from app.services.llm_service import get_llm_service
    from app.services.retrieval_service import get_retrieval_service

    reset_chroma_client()
    get_session_store.cache_clear()
    get_embedding_service.cache_clear()
    get_retrieval_service.cache_clear()
    get_llm_service.cache_clear()


def _reset_scheduler():
    from app.core import scheduler as sched_mod
    sched_mod.stop_scheduler()


def _reset_entity_graph():
    reset_entity_graph_service()


def _run_all_pipeline_workers():
    from app.core.scheduler import ingest_eway_bills, ingest_gst_velocity, ingest_upi_cadence

    ingest_gst_velocity()
    ingest_upi_cadence()
    ingest_eway_bills()


def _hydrate_demo_data() -> None:
    _run_all_pipeline_workers()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "intellicredit-test.db"
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("MODEL_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("PIPELINE_AUTO_START", "false")

    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()
    reset_scorer()
    _reset_service_caches()
    _reset_scheduler()
    _reset_entity_graph()

    import app.main as main_module

    main_module = importlib.reload(main_module)

    with TestClient(main_module.app) as test_client:
        yield test_client

    _reset_scheduler()
    _reset_entity_graph()
    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()
    reset_scorer()
    _reset_service_caches()


@pytest.fixture()
def secured_client(tmp_path, monkeypatch):
    db_path = tmp_path / "intellicredit-secure.db"
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("MODEL_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("REQUIRE_AUTH", "true")
    monkeypatch.setenv("API_TOKENS", "viewer:viewer-token,analyst:analyst-token,admin:admin-token")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("PIPELINE_AUTO_START", "false")

    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()
    reset_scorer()
    _reset_service_caches()
    _reset_scheduler()
    _reset_entity_graph()

    import app.main as main_module

    main_module = importlib.reload(main_module)

    with TestClient(main_module.app) as test_client:
        yield test_client

    _reset_scheduler()
    _reset_entity_graph()
    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()
    reset_scorer()
    _reset_service_caches()


def test_score_endpoint_returns_expected_contract(client):
    _hydrate_demo_data()
    response = client.post("/api/v1/score/29CLEAN5678B1Z2?loan_amount=300000")
    assert response.status_code == 200

    payload = response.json()
    assert payload["gstin"] == "29CLEAN5678B1Z2"
    assert 300 <= payload["credit_score"] <= 900
    assert isinstance(payload["base_score"], int)
    assert payload["model_version"].startswith(("xgb-", "sklearn-gbm-"))
    assert len(payload["top_reasons"]) == 5
    assert "score_freshness" in payload
    assert "data_ingested_at" in payload
    assert "model_inference_at" in payload
    assert "confidence_summary" in payload
    assert "audit_trail" in payload
    assert len(payload["audit_trail"]) >= 1
    assert payload["data_sources"]["source_mode"] == "mocked"
    assert payload["model_backend"] in {"xgboost", "sklearn_gbm", "heuristic"}
    assert payload["freshness_status"] in {"fresh", "stale"}
    assert payload["data_staleness_minutes"] is not None
    assert "calibration" in payload
    assert payload["calibration"]["method"] in {"isotonic_regression_tail_regularized", "isotonic_regression", "identity"}
    assert payload["calibration"]["curve_version"] == payload["model_version"]
    assert payload["percentile"]["score_percentile"] >= 1
    assert payload["calibration_method"] in {"isotonic_regression_tail_regularized", "isotonic_regression", "identity"}
    assert payload["score_mapping"].startswith("non_linear_power_curve_")
    assert 0 <= payload["probability"] <= 1
    assert 0 <= payload["raw_probability"] <= 1
    assert 0 <= payload["default_probability"] <= 1
    assert abs(payload["default_probability"] - (1 - payload["probability"])) < 1e-6
    assert "recommendation_basis" in payload["recommendation"]
    assert "industry_profile" in payload["recommendation"]
    assert payload["requested_loan_amount"] == 300000
    assert payload["counterfactual_recommendations"]["gstin"] == payload["gstin"]
    assert "recommendations" in payload["counterfactual_recommendations"]
    assert payload["counterfactual_recommendations"]["combined_projected_score"] >= payload["counterfactual_recommendations"]["base_score"]
    assert payload["score_trajectory"]["current_score"] == payload["credit_score"]
    assert [point["day"] for point in payload["score_trajectory"]["with_action"]] == [0, 30, 60, 90]
    assert [point["day"] for point in payload["score_trajectory"]["no_action"]] == [0, 30, 60, 90]
    assert payload["score_trajectory"]["target_score_day_90"] >= payload["credit_score"]
    assert payload["lender_recommendations"]["requested_loan_amount"] == 300000
    assert len(payload["lender_recommendations"]["all_lenders"]) == 4
    assert isinstance(payload["owner_narrative"], str)
    assert len(payload["owner_narrative"].split(".")) >= 3


def test_sparse_scenario_sets_sparse_flag_and_short_history(client):
    _hydrate_demo_data()
    response = client.post("/api/v1/score/09NEWCO1234A1Z9")
    assert response.status_code == 200

    payload = response.json()
    assert payload["data_sparse"] is True
    assert payload["pipeline_signals"]["gst_velocity"]["months_active"] <= 5
    assert payload["pipeline_signals"]["upi_cadence"]["months_active"] <= 5
    assert payload["pipeline_signals"]["eway_bill"]["months_active"] <= 5


def test_industry_code_changes_recommendation_amount_and_basis(client):
    _hydrate_demo_data()
    manufacturer = client.post("/api/v1/score/29CLEAN5678B1Z2?industry_code=1701")
    software = client.post("/api/v1/score/29CLEAN5678B1Z2?industry_code=6201")
    assert manufacturer.status_code == 200
    assert software.status_code == 200

    manufacturer_payload = manufacturer.json()
    software_payload = software.json()
    assert manufacturer_payload["industry_profile"]["label"] != software_payload["industry_profile"]["label"]
    assert (
        manufacturer_payload["recommendation"]["recommended_amount"]
        > software_payload["recommendation"]["recommended_amount"]
    )
    assert "manufacturing" in manufacturer_payload["recommendation"]["recommendation_basis"].lower()
    assert "service" in software_payload["recommendation"]["recommendation_basis"].lower()


def test_reject_scenario_records_linked_msme_fraud_alerts(client):
    _hydrate_demo_data()
    response = client.post("/api/v1/score/27ARJUN1234A1Z5")
    assert response.status_code == 200

    payload = response.json()
    assert payload["fraud_detection"]["circular_risk"] == "HIGH"
    assert payload["fraud_detection"]["cross_entity_fraud_detected"] is True
    assert payload["fraud_detection"]["circular_flow_ratio"] > 0.4
    assert len(payload["fraud_detection"]["fraud_ring_members"]) >= 2
    assert payload["fraud_penalty_applied"] is True


def test_history_endpoint_persists_assessments(client):
    _hydrate_demo_data()
    client.post("/api/v1/score/29CLEAN5678B1Z2")
    client.post("/api/v1/score/29CLEAN5678B1Z2")

    history_response = client.get("/api/v1/score/29CLEAN5678B1Z2/history?page=1&page_size=1")
    assert history_response.status_code == 200

    history_payload = history_response.json()
    assert history_payload["total_assessments"] == 2
    assert len(history_payload["history"]) == 1
    assert history_payload["has_more"] is True
    assert "model_version" in history_payload["history"][0]
    assert "data_freshness" in history_payload["history"][0]


def test_apriori_seeding_uses_full_assessment_history(client):
    storage = get_storage()
    base_time = datetime(2026, 4, 4, tzinfo=timezone.utc)

    for idx in range(55):
        created_at = (base_time + timedelta(minutes=idx)).isoformat().replace("+00:00", "Z")
        storage.record_assessment(
            gstin="29CLEAN5678B1Z2" if idx % 3 == 0 else ("27ARJUN1234A1Z5" if idx % 3 == 1 else "09NEWCO1234A1Z9"),
            company_name="Synthetic Demo MSME",
            credit_score=820 if idx % 2 == 0 else 430,
            risk_band="VERY_LOW_RISK" if idx % 2 == 0 else "HIGH_RISK",
            fraud_risk="LOW" if idx % 2 == 0 else "HIGH",
            model_version="test-model",
            industry_code="1701",
            months_active=12.0 if idx % 2 == 0 else 4.0,
            scenario="stable",
            data_sparse=False,
            freshness_timestamp=created_at,
            created_at=created_at,
            top_reasons=[],
            recommendation={
                "eligible": idx % 2 == 0,
                "recommended_amount": 250000,
                "recommended_tenure_months": 24,
            },
            narrative=None,
        )

    seed_status = storage.ensure_mock_loan_outcomes_for_latest_assessments()
    records = storage.get_rule_mining_records()

    assert seed_status["total_outcomes"] >= 50
    assert storage.count_outcome_labeled_records() >= 50
    assert len(records) >= 50


def test_auth_required_when_enabled(secured_client):
    response = secured_client.post("/api/v1/score/29CLEAN5678B1Z2")
    assert response.status_code == 401

    _hydrate_demo_data()
    authed = secured_client.post(
        "/api/v1/score/29CLEAN5678B1Z2",
        headers={"Authorization": "Bearer viewer-token"},
    )
    assert authed.status_code == 200


def test_rate_limit_blocks_excess_requests(secured_client):
    headers = {"Authorization": "Bearer viewer-token"}
    _hydrate_demo_data()
    assert secured_client.post("/api/v1/score/29CLEAN5678B1Z2", headers=headers).status_code == 200
    assert secured_client.post("/api/v1/score/29CLEAN5678B1Z2", headers=headers).status_code == 200
    limited = secured_client.post("/api/v1/score/29CLEAN5678B1Z2", headers=headers)
    assert limited.status_code == 429


def test_analyst_review_persists_audit_entries(secured_client):
    payload = {
        "session_id": "sess-001",
        "company_name": "Test MSME",
        "original_score": 72,
        "overrides": [],
        "management_quality": 4,
        "factory_utilization": 68,
        "field_notes": "Verified on call.",
        "action": "APPROVE",
    }
    headers = {"Authorization": "Bearer analyst-token"}

    response = secured_client.post("/api/analyst/review", json=payload, headers=headers)
    assert response.status_code == 200

    trail = secured_client.get("/api/analyst/audit-trail/sess-001", headers=headers)
    assert trail.status_code == 200
    assert len(trail.json()["entries"]) == 1


def test_invalid_gstin_format_is_rejected(client):
    response = client.post("/api/v1/score/INVALID123")
    assert response.status_code == 400
    assert "Invalid GSTIN format" in response.json()["detail"]


def test_health_reports_model_and_pipeline_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "model" in payload
    assert "fallback_active" in payload["model"]
    assert payload["model"]["calibration_method"] in {"isotonic_regression_tail_regularized", "isotonic_regression", "identity"}
    assert payload["model"]["score_mapping"].startswith("non_linear_power_curve_")
    assert "pipeline_scheduler" in payload
    assert payload["pipeline_scheduler"]["monitored_gstins"] == 3
    assert "entity_graph" in payload


def test_model_metrics_include_calibration_curve(client):
    _hydrate_demo_data()
    response = client.post("/api/v1/score/29CLEAN5678B1Z2")
    assert response.status_code == 200
    metrics = response.json()["model_metrics"]
    assert "calibration_method" in metrics
    assert "raw_model_brier" in metrics
    assert "calibrated_brier" in metrics
    assert "calibration_curve" in metrics
    assert "feature_schema_version" in metrics
    assert isinstance(metrics["calibration_curve"], list)


def test_score_payload_surfaces_gst_amnesty_adjustment(client, monkeypatch):
    monkeypatch.setenv("GST_AMNESTY_ENABLED", "true")
    monkeypatch.setenv("GST_AMNESTY_PERIODS", "2026-01,2026-02,2026-03")
    get_settings.cache_clear()

    _hydrate_demo_data()
    storage = get_storage()
    gstin = "29CLEAN5678B1Z2"
    pipeline_data = storage.get_pipeline_data(gstin)
    assert pipeline_data is not None

    gst_velocity = dict(pipeline_data["gst_velocity"])
    gst_velocity["months_active"] = 12
    gst_velocity["filing_history"] = [
        {"period": "2025-12", "filed": True, "delay_days": 12, "due_date": "2025-12-11", "e_invoice_count": 44, "itc_variance_pct": 4.0},
        {"period": "2026-01", "filed": True, "delay_days": 18, "due_date": "2026-01-11", "e_invoice_count": 46, "itc_variance_pct": 4.5},
        {"period": "2026-02", "filed": True, "delay_days": 15, "due_date": "2026-02-11", "e_invoice_count": 48, "itc_variance_pct": 4.8},
        {"period": "2026-03", "filed": False, "delay_days": None, "due_date": "2026-03-11", "e_invoice_count": 0, "itc_variance_pct": 5.0},
    ]
    gst_velocity["velocity_metrics"] = {
        "filings_per_month": 0.75,
        "avg_delay_days": 15.0,
        "on_time_pct": 0.0,
        "total_e_invoices": 138,
        "e_invoice_trend": "accelerating",
    }
    storage.store_pipeline_data(
        gstin=gstin,
        pipeline_type="gst_velocity",
        epoch=999,
        data=gst_velocity,
        ingested_at=pipeline_data["pipeline_ingested_at"]["gst_velocity"],
    )

    response = client.post(f"/api/v1/score/{gstin}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["gst_policy"]["amnesty_applied"] is True
    assert payload["gst_policy"]["neutralized_late_filings"] == 2
    assert payload["gst_policy"]["excluded_unfiled_periods"] == 1
    assert payload["gst_policy"]["raw_metrics"]["avg_delay_days"] == 15.0
    assert payload["gst_policy"]["adjusted_metrics"]["avg_delay_days"] == 4.0
    assert payload["pipeline_signals"]["gst_velocity"]["avg_delay"] == 4.0
    assert payload["pipeline_signals"]["gst_velocity"]["on_time_pct"] == 66.7


def test_young_business_explanation_uses_maturity_umbrella_reason():
    months = 3
    features = {
        "gst_filing_rate": 0.95,
        "gst_avg_delay_days": POPULATION_DEFAULTS["gst_avg_delay"],
        "gst_on_time_pct": POPULATION_DEFAULTS["gst_on_time_pct"],
        "gst_e_invoice_velocity": POPULATION_DEFAULTS["e_invoice_velocity"],
        "gst_e_invoice_trend": 1.0,
        "gst_itc_variance_avg": 5.0,
        "gst_itc_variance_trend": 0.0,
        "upi_avg_daily_txns": POPULATION_DEFAULTS["upi_daily_txns"],
        "upi_regularity_score": POPULATION_DEFAULTS["upi_regularity"],
        "upi_inflow_outflow_ratio": POPULATION_DEFAULTS["upi_inflow_outflow_ratio"],
        "upi_round_amount_pct": POPULATION_DEFAULTS["upi_round_pct"],
        "upi_net_cash_flow": 0.0,
        "upi_counterparty_diversity": 1.0,
        "upi_volume_growth": 0.0,
        "eway_avg_monthly_bills": POPULATION_DEFAULTS["eway_monthly_bills"],
        "eway_volume_momentum": POPULATION_DEFAULTS["eway_momentum"],
        "eway_mom_growth": 0.0,
        "eway_interstate_ratio": POPULATION_DEFAULTS["eway_interstate_ratio"],
        "eway_cancellation_rate": POPULATION_DEFAULTS["eway_cancellation_rate"],
        "eway_avg_bill_value": 0.0,
        "history_months_active": float(months),
        "gst_filing_history_interaction": round(0.95 * months, 4),
        "upi_regularity_history_interaction": round(POPULATION_DEFAULTS["upi_regularity"] * months, 4),
        "overall_data_confidence": _confidence_weight(months),
    }
    result = get_scorer().score(features)
    assert result["top_reasons"][0]["feature_key"] == "maturity_penalty_umbrella"
    assert "only 3 months of verified history" in result["top_reasons"][0]["reason"]


def test_recommendation_formula_penalizes_low_confidence_and_service_sector():
    manufacturing_high_conf = recommend_loan(
        700,
        500000,
        industry_code="1701",
        data_confidence=0.95,
        months_active=18,
    )
    services_high_conf = recommend_loan(
        700,
        500000,
        industry_code="6201",
        data_confidence=0.95,
        months_active=18,
    )
    manufacturing_low_conf = recommend_loan(
        700,
        500000,
        industry_code="1701",
        data_confidence=0.4,
        months_active=3,
    )
    assert manufacturing_high_conf["recommended_amount"] > services_high_conf["recommended_amount"]
    assert manufacturing_high_conf["recommended_amount"] > manufacturing_low_conf["recommended_amount"]
    assert manufacturing_low_conf["confidence_multiplier"] < manufacturing_high_conf["confidence_multiplier"]


def test_stale_pipeline_data_triggers_manual_review(client):
    _hydrate_demo_data()
    storage = get_storage()
    pipeline_data = storage.get_pipeline_data("29CLEAN5678B1Z2")
    assert pipeline_data is not None

    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    storage.store_pipeline_data(
        gstin="29CLEAN5678B1Z2",
        pipeline_type="upi_cadence",
        epoch=storage.get_pipeline_epoch("29CLEAN5678B1Z2", "upi_cadence"),
        data=pipeline_data["upi_cadence"],
        ingested_at=stale_ts,
    )

    response = client.post("/api/v1/score/29CLEAN5678B1Z2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["freshness_status"] == "stale"
    assert payload["manual_review_required"] is True
    assert payload["recommendation"]["manual_review_required"] is True
    assert payload["score_freshness"] == stale_ts
    assert payload["data_staleness_minutes"] >= 120


def test_expired_pipeline_data_returns_202_and_reingests(client):
    _hydrate_demo_data()
    storage = get_storage()
    pipeline_data = storage.get_pipeline_data("29CLEAN5678B1Z2")
    assert pipeline_data is not None

    expired_ts = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    storage.store_pipeline_data(
        gstin="29CLEAN5678B1Z2",
        pipeline_type="gst_velocity",
        epoch=storage.get_pipeline_epoch("29CLEAN5678B1Z2", "gst_velocity"),
        data=pipeline_data["gst_velocity"],
        ingested_at=expired_ts,
    )

    response = client.post("/api/v1/score/29CLEAN5678B1Z2")
    assert response.status_code == 202
    assert "expired" in response.json()["detail"].lower()
    assert "Retry-After" in response.headers


def test_export_docx_endpoint_returns_document(client):
    _hydrate_demo_data()
    client.post("/api/v1/score/29CLEAN5678B1Z2")
    response = client.get("/api/v1/score/29CLEAN5678B1Z2/export.docx")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_scenario_is_derived_from_model_output(client):
    """Verify that the scenario label is derived post-hoc from the model's
    actual score rather than being pre-determined by the GSTIN input."""
    _hydrate_demo_data()
    response = client.post("/api/v1/score/29CLEAN5678B1Z2")
    payload = response.json()
    if payload["data_sparse"]:
        assert payload["scenario"] == "sparse"
    elif payload["credit_score"] >= 650:
        assert payload["scenario"] == "approve"
    else:
        assert payload["scenario"] == "reject"


def test_first_time_gstin_returns_202_until_background_ingestion_runs(client):
    response = client.post("/api/v1/score/07ABCDE1234F1Z5")
    assert response.status_code == 202
    assert "Retry-After" in response.headers
    assert "ingestion in progress" in response.json()["detail"].lower()

    _run_all_pipeline_workers()

    retry = client.post("/api/v1/score/07ABCDE1234F1Z5")
    assert retry.status_code == 200
    payload = retry.json()
    assert 300 <= payload["credit_score"] <= 900
    assert len(payload["top_reasons"]) >= 1
    assert payload["scenario"] in {"approve", "reject", "sparse"}


def test_pipeline_data_is_read_from_store(client):
    """Verify that the scoring endpoint reads from the pipeline data store
    and that the same GSTIN returns the same score within the same epoch."""
    _hydrate_demo_data()
    r1 = client.post("/api/v1/score/29CLEAN5678B1Z2")
    r2 = client.post("/api/v1/score/29CLEAN5678B1Z2")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same underlying pipeline data → same credit score
    assert r1.json()["credit_score"] == r2.json()["credit_score"]

def test_simulate_endpoint_returns_projection(client):
    _hydrate_demo_data()
    response = client.get("/api/v1/score/27ARJUN1234A1Z5/simulate")
    assert response.status_code == 200

    payload = response.json()
    assert payload["gstin"] == "27ARJUN1234A1Z5"
    assert payload["combined_projected_score"] >= payload["base_score"]
    assert payload["combined_score_improvement"] >= 0
    assert payload["naive_sum_score_improvement"] >= payload["combined_score_improvement"]
    assert len(payload["recommendations"]) >= 1
    top = payload["recommendations"][0]
    assert "feature_name" in top
    assert "current_value_display" in top
    assert "target_value_display" in top
    assert top["estimated_score_improvement"] > 0
    assert top["confidence"] in {"high", "medium"}
    assert top["timeframe_days"]


def test_counterfactual_engine_recommends_gst_filing_rate_and_manual_rescore_matches_delta():
    scorer = get_scorer()
    engine = CounterfactualEngine()
    feature_vector = {
        "gst_filing_rate": 0.67,
        "gst_avg_delay_days": 8.03,
        "gst_on_time_pct": 60.72,
        "gst_e_invoice_velocity": 15.67,
        "gst_e_invoice_trend": 1.0,
        "gst_itc_variance_avg": 13.92,
        "gst_itc_variance_trend": 0.161,
        "upi_avg_daily_txns": 2.5,
        "upi_regularity_score": 36.6,
        "upi_inflow_outflow_ratio": 0.896,
        "upi_round_amount_pct": 19.91,
        "upi_net_cash_flow": -25000.0,
        "upi_counterparty_diversity": 0.87,
        "upi_volume_growth": 2.37,
        "eway_avg_monthly_bills": 8.61,
        "eway_volume_momentum": -3.1,
        "eway_mom_growth": -7.74,
        "eway_interstate_ratio": 26.53,
        "eway_cancellation_rate": 11.87,
        "eway_avg_bill_value": 215039.0,
        "history_months_active": 8.58,
        "overall_data_confidence": 0.83,
    }
    feature_vector["gst_filing_history_interaction"] = round(
        feature_vector["gst_filing_rate"] * feature_vector["history_months_active"],
        4,
    )
    feature_vector["upi_regularity_history_interaction"] = round(
        feature_vector["upi_regularity_score"] * feature_vector["history_months_active"],
        4,
    )

    current_score = scorer.predict_credit_score(feature_vector)
    result = engine.generate_recommendations(
        gstin="27VERIFYGSTIN1Z5",
        feature_vector=feature_vector,
        current_score=current_score,
        model=scorer,
    )

    assert current_score == 614
    assert result["recommendations"][0]["feature_key"] == "gst_filing_rate"

    recommendation = result["recommendations"][0]
    recommended_vector = engine._apply_feature_change(
        feature_vector,
        recommendation["feature_key"],
        recommendation["target_value"],
    )
    rescored = scorer.predict_credit_score(recommended_vector)
    stated_projection = current_score + recommendation["estimated_score_improvement"]

    assert abs(rescored - stated_projection) <= 5


def test_lender_matcher_groups_qualified_and_borderline_lenders():
    matcher = LenderMatcher()

    result = matcher.match_lenders(
        score=690,
        fraud_score=30,
        loan_amount=250000,
        history_months=5,
    )

    assert result["recommended_lender"]["key"] == "mfi"
    assert any(lender["key"] == "nbfc" for lender in result["borderline_lenders"])
    nbfc = next(lender for lender in result["borderline_lenders"] if lender["key"] == "nbfc")
    assert "1 more months of history" in nbfc["gap_statement"]
    assert any(lender["key"] == "commercial_bank" for lender in result["not_yet_accessible_lenders"])


def test_trajectory_projector_returns_curves_and_unlock_events():
    scorer = get_scorer()
    engine = CounterfactualEngine()
    projector = TrajectoryProjector(counterfactual_engine=engine)
    feature_vector = {
        "gst_filing_rate": 0.67,
        "gst_avg_delay_days": 8.03,
        "gst_on_time_pct": 60.72,
        "gst_e_invoice_velocity": 15.67,
        "gst_e_invoice_trend": 1.0,
        "gst_itc_variance_avg": 13.92,
        "gst_itc_variance_trend": 0.161,
        "upi_avg_daily_txns": 2.5,
        "upi_regularity_score": 36.6,
        "upi_inflow_outflow_ratio": 0.896,
        "upi_round_amount_pct": 19.91,
        "upi_net_cash_flow": -25000.0,
        "upi_counterparty_diversity": 0.87,
        "upi_volume_growth": 2.37,
        "eway_avg_monthly_bills": 8.61,
        "eway_volume_momentum": -3.1,
        "eway_mom_growth": -7.74,
        "eway_interstate_ratio": 26.53,
        "eway_cancellation_rate": 11.87,
        "eway_avg_bill_value": 215039.0,
        "history_months_active": 5.2,
        "overall_data_confidence": 0.83,
    }
    feature_vector["gst_filing_history_interaction"] = round(
        feature_vector["gst_filing_rate"] * feature_vector["history_months_active"],
        4,
    )
    feature_vector["upi_regularity_history_interaction"] = round(
        feature_vector["upi_regularity_score"] * feature_vector["history_months_active"],
        4,
    )
    current_score = scorer.predict_credit_score(feature_vector)
    counterfactual = engine.generate_recommendations(
        gstin="27VERIFYGSTIN1Z5",
        feature_vector=feature_vector,
        current_score=current_score,
        model=scorer,
    )

    result = projector.project(
        feature_vector=feature_vector,
        current_score=current_score,
        counterfactual_result=counterfactual,
        model=scorer,
        fraud_score=20,
        loan_amount=250000,
        history_months=feature_vector["history_months_active"],
    )

    assert [point["day"] for point in result["with_action"]] == [0, 30, 60, 90]
    assert [point["day"] for point in result["no_action"]] == [0, 30, 60, 90]
    assert result["with_action"][0]["score"] == current_score
    assert result["target_score_day_90"] == result["with_action"][-1]["score"]
    assert result["target_score_day_90"] >= current_score
    assert result["no_action"][-1]["score"] == current_score + 6
    assert any(event["lender_key"] == "mfi" for event in result["lender_unlock_events"])


def test_refresh_endpoint_updates_pipeline_timestamp(client):
    _hydrate_demo_data()
    first = client.post("/api/v1/score/29CLEAN5678B1Z2")
    assert first.status_code == 200
    first_timestamp = first.json()["data_ingested_at"]

    refreshed = client.post("/api/v1/score/29CLEAN5678B1Z2/refresh")
    assert refreshed.status_code == 200

    second = client.post("/api/v1/score/29CLEAN5678B1Z2")
    assert second.status_code == 200
    assert second.json()["data_ingested_at"] != first_timestamp


def test_entity_graph_endpoint_returns_cytoscape_contract(client):
    _hydrate_demo_data()
    response = client.get("/api/v1/entity-graph/27ARJUN1234A1Z5")
    assert response.status_code == 200
    payload = response.json()
    assert "nodes" in payload
    assert "edges" in payload
    assert "meta" in payload
    assert payload["meta"]["cycles_detected"] >= 1
    assert any(node["data"]["is_queried"] for node in payload["nodes"])


def test_pipeline_workers_update_data(tmp_path, monkeypatch):
    """Verify that running a pipeline worker changes the epoch and data."""
    db_path = tmp_path / "intellicredit-workers.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("PIPELINE_AUTO_START", "false")

    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()
    _reset_scheduler()

    from app.core.scheduler import ingest_gst_velocity, seed_demo_gstins
    from app.core.storage import get_storage

    seed_demo_gstins()
    storage = get_storage()

    epoch_before = storage.get_pipeline_epoch("29CLEAN5678B1Z2", "gst_velocity")
    ingest_gst_velocity()
    epoch_after = storage.get_pipeline_epoch("29CLEAN5678B1Z2", "gst_velocity")

    assert epoch_before == 0
    assert epoch_after == epoch_before + 1

    _reset_scheduler()
    get_settings.cache_clear()
    storage_module._storage = None
    reset_database_runtime()


def test_retrain_endpoint_uses_real_feedback_and_logs_model_version(secured_client, monkeypatch):
    _hydrate_demo_data()
    from app.api import scoring_endpoint as scoring_endpoint_module
    from app.core import xgboost_model as xgb_model_module

    monkeypatch.setattr(xgb_model_module, "REAL_OUTCOME_MIN_RECORDS", 2)
    monkeypatch.setattr(scoring_endpoint_module, "REAL_OUTCOME_MIN_RECORDS", 2)
    reset_scorer()

    pending = secured_client.post(
        "/api/v1/model/retrain",
        json={
            "outcomes": [
                {
                    "gstin": "29CLEAN5678B1Z2",
                    "outcome": "repaid",
                    "loan_amount": 1500000,
                    "tenure_months": 24,
                    "company_name": "CleanTech Manufacturing Ltd.",
                }
            ]
        },
        headers={"Authorization": "Bearer admin-token"},
    )
    # fixture does not require auth; route still accepts the header harmlessly
    assert pending.status_code == 200
    pending_payload = pending.json()
    assert pending_payload["retrained"] is False
    assert pending_payload["total_real_outcomes"] == 1

    retrained = secured_client.post(
        "/api/v1/model/retrain",
        json={
            "outcomes": [
                {
                    "gstin": "27ARJUN1234A1Z5",
                    "outcome": "defaulted",
                    "loan_amount": 900000,
                    "tenure_months": 12,
                    "company_name": "Arjun Textiles Pvt. Ltd.",
                }
            ]
        },
        headers={"Authorization": "Bearer admin-token"},
    )
    assert retrained.status_code == 200
    payload = retrained.json()
    assert payload["retrained"] is True
    assert payload["governance"]["real_outcomes_used"] >= 2
    assert payload["governance"]["training_sample_size"] >= payload["governance"]["real_outcomes_used"]
    assert payload["governance"]["auc_after"] is not None
    assert payload["governance"]["feature_schema_version"]

    versions = get_storage().get_model_versions(limit=5)
    assert versions
    assert versions[0]["model_version"] == payload["model"]["model_version"]
    assert versions[0]["feature_schema_version"] == payload["governance"]["feature_schema_version"]
