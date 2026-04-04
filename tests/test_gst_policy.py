from app.core.settings import get_settings
from app.services.feature_engineering import extract_gst_features
from app.services.gst_policy import summarize_gst_amnesty_policy


def test_gst_amnesty_summary_neutralizes_late_filings(monkeypatch):
    monkeypatch.setenv("GST_AMNESTY_ENABLED", "true")
    monkeypatch.setenv("GST_AMNESTY_START", "2026-01")
    monkeypatch.setenv("GST_AMNESTY_END", "2026-03")
    get_settings.cache_clear()

    gst_data = {
        "months_active": 4,
        "filing_history": [
            {"period": "2025-12", "filed": True, "delay_days": 14, "due_date": "2025-12-11", "e_invoice_count": 10, "itc_variance_pct": 4.0},
            {"period": "2026-01", "filed": True, "delay_days": 20, "due_date": "2026-01-11", "e_invoice_count": 11, "itc_variance_pct": 5.0},
            {"period": "2026-02", "filed": False, "delay_days": None, "due_date": "2026-02-11", "e_invoice_count": 0, "itc_variance_pct": 6.0},
            {"period": "2026-03", "filed": True, "delay_days": 16, "due_date": "2026-03-11", "e_invoice_count": 12, "itc_variance_pct": 7.0},
        ],
        "velocity_metrics": {
            "filings_per_month": 0.75,
            "avg_delay_days": 16.7,
            "on_time_pct": 0.0,
            "e_invoice_trend": "accelerating",
        },
        "itc_variance_trend": [4.0, 5.0, 6.0, 7.0],
    }

    summary = summarize_gst_amnesty_policy(gst_data)

    assert summary["amnesty_applied"] is True
    assert summary["covered_periods"] == ["2026-01", "2026-02", "2026-03"]
    assert summary["neutralized_late_filings"] == 2
    assert summary["excluded_unfiled_periods"] == 1
    assert summary["raw_metrics"]["filings_per_month"] == 0.75
    assert summary["adjusted_metrics"]["filings_per_month"] == 1.0
    assert summary["adjusted_metrics"]["avg_delay_days"] == 4.7
    assert summary["adjusted_metrics"]["on_time_pct"] == 66.7

    get_settings.cache_clear()


def test_extract_gst_features_uses_amnesty_adjusted_metrics(monkeypatch):
    monkeypatch.setenv("GST_AMNESTY_ENABLED", "true")
    monkeypatch.setenv("GST_AMNESTY_PERIODS", "2026-01,2026-02,2026-03")
    get_settings.cache_clear()

    gst_data = {
        "months_active": 12,
        "filing_history": [
            {"period": "2025-12", "filed": True, "delay_days": 12, "due_date": "2025-12-11", "e_invoice_count": 40, "itc_variance_pct": 4.0},
            {"period": "2026-01", "filed": True, "delay_days": 18, "due_date": "2026-01-11", "e_invoice_count": 42, "itc_variance_pct": 4.5},
            {"period": "2026-02", "filed": True, "delay_days": 15, "due_date": "2026-02-11", "e_invoice_count": 44, "itc_variance_pct": 5.0},
            {"period": "2026-03", "filed": False, "delay_days": None, "due_date": "2026-03-11", "e_invoice_count": 0, "itc_variance_pct": 5.5},
        ],
        "velocity_metrics": {
            "filings_per_month": 0.75,
            "avg_delay_days": 15.0,
            "on_time_pct": 0.0,
            "e_invoice_trend": "accelerating",
        },
        "itc_variance_trend": [4.0, 4.5, 5.0, 5.5],
    }

    features = extract_gst_features(gst_data)

    assert features["gst_filing_rate"] == 1.0
    assert features["gst_avg_delay_days"] == 4.0
    assert features["gst_on_time_pct"] == 100.0

    get_settings.cache_clear()
