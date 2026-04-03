"""
Feature engineering layer for real-time MSME credit signals.
Transforms raw time-series pipeline data into ML-ready features.

Handles sparse data gracefully — a 3-month-old MSME gets imputed
features with appropriate confidence penalties.
"""

from typing import Any, Dict, Optional

import numpy as np


# ──────────────────────────────────────────────────────────
#  SPARSE DATA IMPUTATION
# ──────────────────────────────────────────────────────────

# Minimum months for full confidence; below this, features are penalized
MIN_MONTHS_FULL_CONFIDENCE = 12
MIN_MONTHS_USABLE = 3

# Population defaults (calibrated from RBI/SIDBI data) used when data is sparse
POPULATION_DEFAULTS = {
    "gst_filing_rate": 0.85,
    "gst_avg_delay": 8.0,
    "gst_on_time_pct": 75.0,
    "e_invoice_velocity": 30.0,
    "upi_daily_txns": 10.0,
    "upi_regularity": 70.0,
    "upi_inflow_outflow_ratio": 1.0,
    "upi_round_pct": 15.0,
    "eway_monthly_bills": 20.0,
    "eway_momentum": 0.0,
    "eway_interstate_ratio": 40.0,
    "eway_cancellation_rate": 5.0,
}


def _confidence_weight(months_active: int) -> float:
    """
    Returns a confidence weight [0.3, 1.0] based on data history length.
    3 months → 0.3, 6 months → 0.5, 12+ months → 1.0
    """
    if months_active >= MIN_MONTHS_FULL_CONFIDENCE:
        return 1.0
    if months_active < MIN_MONTHS_USABLE:
        return 0.3
    return 0.3 + 0.7 * (months_active - MIN_MONTHS_USABLE) / (MIN_MONTHS_FULL_CONFIDENCE - MIN_MONTHS_USABLE)


def _blend_with_default(observed: float, default: float, confidence: float) -> float:
    """Blend observed value with population default based on confidence."""
    return observed * confidence + default * (1 - confidence)


# ──────────────────────────────────────────────────────────
#  GST FEATURES
# ──────────────────────────────────────────────────────────

def extract_gst_features(gst_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract ML features from GST velocity pipeline data.

    Features:
        - gst_filing_rate: % of months with a filing (0-1)
        - gst_avg_delay_days: average days past due date
        - gst_on_time_pct: % filed within 10 days of due
        - gst_e_invoice_velocity: avg monthly e-invoice count
        - gst_e_invoice_trend: 1=accelerating, 0=stable, -1=decelerating
        - gst_itc_variance_avg: average ITC variance across months
        - gst_itc_variance_trend: slope of ITC variance (positive = worsening)
        - gst_data_confidence: confidence weight based on history length
    """
    months = gst_data.get("months_active", 0)
    confidence = _confidence_weight(months)
    metrics = gst_data.get("velocity_metrics", {})
    history = gst_data.get("filing_history", [])

    filing_rate = metrics.get("filings_per_month", POPULATION_DEFAULTS["gst_filing_rate"])
    avg_delay = metrics.get("avg_delay_days", POPULATION_DEFAULTS["gst_avg_delay"])
    on_time = metrics.get("on_time_pct", POPULATION_DEFAULTS["gst_on_time_pct"])

    # E-invoice velocity
    e_inv_counts = [h.get("e_invoice_count", 0) for h in history if h.get("filed")]
    e_inv_velocity = np.mean(e_inv_counts) if e_inv_counts else POPULATION_DEFAULTS["e_invoice_velocity"]
    e_inv_trend = 1.0 if metrics.get("e_invoice_trend") == "accelerating" else -1.0

    # ITC variance trend (slope via simple linear regression)
    itc_vars = gst_data.get("itc_variance_trend", [])
    if len(itc_vars) >= 3:
        x = np.arange(len(itc_vars))
        slope = np.polyfit(x, itc_vars, 1)[0]
        itc_avg = np.mean(itc_vars)
    else:
        slope = 0.0
        itc_avg = np.mean(itc_vars) if itc_vars else 5.0

    return {
        "gst_filing_rate": _blend_with_default(filing_rate, POPULATION_DEFAULTS["gst_filing_rate"], confidence),
        "gst_avg_delay_days": _blend_with_default(avg_delay, POPULATION_DEFAULTS["gst_avg_delay"], confidence),
        "gst_on_time_pct": _blend_with_default(on_time, POPULATION_DEFAULTS["gst_on_time_pct"], confidence),
        "gst_e_invoice_velocity": _blend_with_default(e_inv_velocity, POPULATION_DEFAULTS["e_invoice_velocity"], confidence),
        "gst_e_invoice_trend": e_inv_trend,
        "gst_itc_variance_avg": round(itc_avg, 2),
        "gst_itc_variance_trend": round(slope, 3),
        "gst_data_confidence": round(confidence, 2),
    }


# ──────────────────────────────────────────────────────────
#  UPI FEATURES
# ──────────────────────────────────────────────────────────

def extract_upi_features(upi_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract ML features from UPI cadence pipeline data.

    Features:
        - upi_avg_daily_txns: average daily transaction count
        - upi_regularity_score: cadence consistency (0-100)
        - upi_inflow_outflow_ratio: inflow/outflow volume ratio
        - upi_round_amount_pct: % of round-number transactions (rotation signal)
        - upi_net_cash_flow: net monthly cash position (normalized)
        - upi_counterparty_diversity: unique counterparties / total txns
        - upi_volume_growth: MoM volume growth rate
        - upi_data_confidence: confidence weight
    """
    months = upi_data.get("months_active", 0)
    confidence = _confidence_weight(months)
    metrics = upi_data.get("cadence_metrics", {})
    flow = upi_data.get("flow_pattern", {})
    cpty = upi_data.get("counterparty_analysis", {})
    monthly = upi_data.get("monthly_summary", [])

    avg_daily = metrics.get("avg_daily_txns", POPULATION_DEFAULTS["upi_daily_txns"])
    regularity = metrics.get("regularity_score", POPULATION_DEFAULTS["upi_regularity"])
    io_ratio = flow.get("inflow_outflow_ratio", POPULATION_DEFAULTS["upi_inflow_outflow_ratio"])
    round_pct = flow.get("round_amount_pct", POPULATION_DEFAULTS["upi_round_pct"])
    net_cash = flow.get("net_cash_position", 0)

    # Volume growth: last 3 months vs first 3 months
    if len(monthly) >= 6:
        recent = sum(m["total_txns"] for m in monthly[-3:])
        early = sum(m["total_txns"] for m in monthly[:3])
        volume_growth = (recent - early) / max(early, 1) * 100
    else:
        volume_growth = 0.0

    # Counterparty diversity
    total_txns = metrics.get("total_transactions", 1)
    unique_cpty = cpty.get("unique_counterparties", 1)
    diversity = unique_cpty / max(total_txns / 30, 1)  # Normalized

    return {
        "upi_avg_daily_txns": _blend_with_default(avg_daily, POPULATION_DEFAULTS["upi_daily_txns"], confidence),
        "upi_regularity_score": _blend_with_default(regularity, POPULATION_DEFAULTS["upi_regularity"], confidence),
        "upi_inflow_outflow_ratio": _blend_with_default(io_ratio, POPULATION_DEFAULTS["upi_inflow_outflow_ratio"], confidence),
        "upi_round_amount_pct": _blend_with_default(round_pct, POPULATION_DEFAULTS["upi_round_pct"], confidence),
        "upi_net_cash_flow": round(net_cash),
        "upi_counterparty_diversity": round(min(diversity, 5.0), 2),
        "upi_volume_growth": round(volume_growth, 1),
        "upi_data_confidence": round(confidence, 2),
    }


# ──────────────────────────────────────────────────────────
#  E-WAY BILL FEATURES
# ──────────────────────────────────────────────────────────

def extract_eway_features(eway_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract ML features from e-way bill volume pipeline data.

    Features:
        - eway_avg_monthly_bills: average bill count per month
        - eway_volume_momentum: growth rate of recent vs early period
        - eway_mom_growth: average month-on-month growth
        - eway_interstate_ratio: % of interstate movement
        - eway_cancellation_rate: % of cancelled bills (fraud signal)
        - eway_avg_bill_value: average per-bill value
        - eway_data_confidence: confidence weight
    """
    months = eway_data.get("months_active", 0)
    confidence = _confidence_weight(months)
    trends = eway_data.get("trend_metrics", {})
    monthly = eway_data.get("monthly_volumes", [])
    anomalies = eway_data.get("anomaly_flags", [])

    avg_bills = trends.get("avg_bills_per_month", POPULATION_DEFAULTS["eway_monthly_bills"])
    momentum = trends.get("volume_momentum_pct", POPULATION_DEFAULTS["eway_momentum"])
    mom_growth = trends.get("avg_mom_growth_pct", 0.0)
    interstate = trends.get("interstate_ratio", POPULATION_DEFAULTS["eway_interstate_ratio"])

    # Cancellation rate
    total_bills = sum(m["bill_count"] for m in monthly) if monthly else 1
    total_cancelled = sum(m["cancelled_count"] for m in monthly) if monthly else 0
    cancel_rate = total_cancelled / max(total_bills, 1) * 100

    # Average bill value
    total_value = sum(m["total_value"] for m in monthly) if monthly else 0
    avg_value = total_value / max(total_bills, 1)

    return {
        "eway_avg_monthly_bills": _blend_with_default(avg_bills, POPULATION_DEFAULTS["eway_monthly_bills"], confidence),
        "eway_volume_momentum": _blend_with_default(momentum, POPULATION_DEFAULTS["eway_momentum"], confidence),
        "eway_mom_growth": round(mom_growth, 1),
        "eway_interstate_ratio": _blend_with_default(interstate, POPULATION_DEFAULTS["eway_interstate_ratio"], confidence),
        "eway_cancellation_rate": _blend_with_default(cancel_rate, POPULATION_DEFAULTS["eway_cancellation_rate"], confidence),
        "eway_avg_bill_value": round(avg_value),
        "eway_data_confidence": round(confidence, 2),
    }


# ──────────────────────────────────────────────────────────
#  COMBINED FEATURE VECTOR
# ──────────────────────────────────────────────────────────

def build_feature_vector(pipeline_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Build complete ML feature vector from all three pipeline outputs.
    Returns a flat dict of ~23 features ready for model input.
    """
    gst_features = extract_gst_features(pipeline_data.get("gst_velocity", {}))
    upi_features = extract_upi_features(pipeline_data.get("upi_cadence", {}))
    eway_features = extract_eway_features(pipeline_data.get("eway_bill", {}))

    # Compute overall data confidence (min of all three — weakest link)
    overall_confidence = min(
        gst_features["gst_data_confidence"],
        upi_features["upi_data_confidence"],
        eway_features["eway_data_confidence"],
    )

    features = {
        **gst_features,
        **upi_features,
        **eway_features,
        "history_months_active": float(
            min(
                pipeline_data.get("gst_velocity", {}).get("months_active", 0),
                pipeline_data.get("upi_cadence", {}).get("months_active", 0),
                pipeline_data.get("eway_bill", {}).get("months_active", 0),
            )
        ),
    }
    features["gst_filing_history_interaction"] = round(
        features["gst_filing_rate"] * features["history_months_active"],
        4,
    )
    features["upi_regularity_history_interaction"] = round(
        features["upi_regularity_score"] * features["history_months_active"],
        4,
    )
    features["overall_data_confidence"] = overall_confidence

    return features


# Feature names in fixed order for model input
FEATURE_NAMES = [
    "gst_filing_rate", "gst_avg_delay_days", "gst_on_time_pct",
    "gst_e_invoice_velocity", "gst_e_invoice_trend",
    "gst_itc_variance_avg", "gst_itc_variance_trend",
    "upi_avg_daily_txns", "upi_regularity_score",
    "upi_inflow_outflow_ratio", "upi_round_amount_pct",
    "upi_net_cash_flow", "upi_counterparty_diversity", "upi_volume_growth",
    "eway_avg_monthly_bills", "eway_volume_momentum", "eway_mom_growth",
    "eway_interstate_ratio", "eway_cancellation_rate", "eway_avg_bill_value",
    "history_months_active",
    "gst_filing_history_interaction",
    "upi_regularity_history_interaction",
    "overall_data_confidence",
]


def features_to_array(features: Dict[str, float]) -> list:
    """Convert feature dict to ordered array for model input."""
    return [features.get(name, 0.0) for name in FEATURE_NAMES]
