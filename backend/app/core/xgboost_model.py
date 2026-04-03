"""
Gradient-boosted MSME credit scoring with artifact-backed model loading.
Persists a trained model to disk and reloads it on startup instead of retraining
for every server process.
"""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

try:
    import shap
except ImportError:  # pragma: no cover - dependency presence varies by env
    shap = None

try:
    import xgboost as xgb

    HAS_XGB = True
except ImportError:  # pragma: no cover - dependency presence varies by env
    xgb = None
    HAS_XGB = False

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.isotonic import IsotonicRegression
    from sklearn.metrics import (
        accuracy_score,
        brier_score_loss,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import GroupShuffleSplit, train_test_split

    HAS_SKLEARN_GBM = True
except ImportError:  # pragma: no cover - dependency presence varies by env
    GradientBoostingClassifier = None
    IsotonicRegression = None
    accuracy_score = brier_score_loss = precision_score = recall_score = roc_auc_score = None
    GroupShuffleSplit = None
    train_test_split = None
    HAS_SKLEARN_GBM = False

from ..services.feature_engineering import FEATURE_NAMES
from .settings import get_settings


TRAINING_SCHEMA_ID = "lagged-panel-interactions-v12-tail-calibrated-real-feedback"
SCORE_CURVE_EXPONENT = 1.1
REAL_OUTCOME_MIN_RECORDS = 50
TAIL_SHRINK_THRESHOLD = 0.90
TAIL_SHRINK_FACTOR = 0.35
TAIL_SHRINK_CAP = 0.94
INTERACTION_REASON_KEYS = {
    "gst_filing_history_interaction",
    "upi_regularity_history_interaction",
}

RISK_BANDS = [
    (800, 900, "VERY_LOW_RISK", "Excellent credit profile — pre-approved track"),
    (700, 799, "LOW_RISK", "Strong credit profile — standard processing"),
    (600, 699, "MODERATE_RISK", "Acceptable with conditions — enhanced monitoring"),
    (500, 599, "HIGH_RISK", "Elevated risk — requires additional collateral"),
    (300, 499, "VERY_HIGH_RISK", "Unacceptable risk — decline recommended"),
]

INDUSTRY_PROFILES = {
    "01": {
        "label": "Agriculture and allied activities",
        "amount_multiplier": 0.95,
        "tenure_options_months": [12, 18, 24],
        "repayment_structure": "seasonal_cash_flow",
        "basis_phrase": "seasonal agriculture cash-flow cycle",
    },
    "10": {
        "label": "Food manufacturing",
        "amount_multiplier": 1.12,
        "tenure_options_months": [24, 36, 48],
        "repayment_structure": "inventory_backed_monthly",
        "basis_phrase": "manufacturing inventory profile",
    },
    "13": {
        "label": "Textiles manufacturing",
        "amount_multiplier": 1.15,
        "tenure_options_months": [24, 36, 48],
        "repayment_structure": "inventory_backed_monthly",
        "basis_phrase": "textile working-capital cycle",
    },
    "17": {
        "label": "Paper and packaging manufacturing",
        "amount_multiplier": 1.14,
        "tenure_options_months": [24, 36, 48],
        "repayment_structure": "inventory_backed_monthly",
        "basis_phrase": "asset-backed manufacturing sector profile",
    },
    "41": {
        "label": "Construction and project services",
        "amount_multiplier": 1.05,
        "tenure_options_months": [18, 24, 36],
        "repayment_structure": "milestone_aligned",
        "basis_phrase": "project-based cash conversion profile",
    },
    "46": {
        "label": "Wholesale trade",
        "amount_multiplier": 1.02,
        "tenure_options_months": [12, 18, 24],
        "repayment_structure": "working_capital_monthly",
        "basis_phrase": "trade working-capital profile",
    },
    "47": {
        "label": "Retail trade",
        "amount_multiplier": 0.98,
        "tenure_options_months": [12, 18, 24],
        "repayment_structure": "working_capital_monthly",
        "basis_phrase": "retail turnover profile",
    },
    "49": {
        "label": "Transport and logistics",
        "amount_multiplier": 1.06,
        "tenure_options_months": [24, 36],
        "repayment_structure": "fleet_cash_flow_monthly",
        "basis_phrase": "fleet and route cash-flow profile",
    },
    "55": {
        "label": "Tourism and hospitality",
        "amount_multiplier": 0.9,
        "tenure_options_months": [12, 18, 24],
        "repayment_structure": "seasonal_cash_flow",
        "basis_phrase": "seasonal tourism demand cycle",
    },
    "56": {
        "label": "Food service and hospitality",
        "amount_multiplier": 0.92,
        "tenure_options_months": [12, 18, 24],
        "repayment_structure": "seasonal_cash_flow",
        "basis_phrase": "hospitality seasonality profile",
    },
    "62": {
        "label": "Software and IT services",
        "amount_multiplier": 0.82,
        "tenure_options_months": [12, 24],
        "repayment_structure": "receivables_based_monthly",
        "basis_phrase": "service-business receivables profile",
    },
    "69": {
        "label": "Professional services",
        "amount_multiplier": 0.85,
        "tenure_options_months": [12, 24],
        "repayment_structure": "receivables_based_monthly",
        "basis_phrase": "professional services receivables profile",
    },
    "86": {
        "label": "Healthcare services",
        "amount_multiplier": 0.96,
        "tenure_options_months": [18, 24, 36],
        "repayment_structure": "steady_cash_flow_monthly",
        "basis_phrase": "steady healthcare cash-flow profile",
    },
}

DEFAULT_INDUSTRY_PROFILE = {
    "label": "General MSME",
    "amount_multiplier": 1.0,
    "tenure_options_months": [12, 24, 36],
    "repayment_structure": "standard_monthly",
    "basis_phrase": "general MSME cash-flow profile",
}

FEATURE_DISPLAY_NAMES = {
    "gst_filing_rate": "GST Filing Regularity",
    "gst_avg_delay_days": "GST Filing Delay (days)",
    "gst_on_time_pct": "GST On-Time Filing Rate",
    "gst_e_invoice_velocity": "E-Invoice Generation Speed",
    "gst_e_invoice_trend": "E-Invoice Growth Trend",
    "gst_itc_variance_avg": "ITC Claim Variance",
    "gst_itc_variance_trend": "ITC Variance Trend (worsening)",
    "upi_avg_daily_txns": "UPI Daily Transaction Volume",
    "upi_regularity_score": "UPI Payment Regularity",
    "upi_inflow_outflow_ratio": "Cash Inflow vs Outflow Ratio",
    "upi_round_amount_pct": "Round-Amount Transaction Rate",
    "upi_net_cash_flow": "Net UPI Cash Position",
    "upi_counterparty_diversity": "Payment Counterparty Diversity",
    "upi_volume_growth": "UPI Volume Growth Rate",
    "eway_avg_monthly_bills": "E-Way Bill Monthly Volume",
    "eway_volume_momentum": "Shipment Volume Momentum",
    "eway_mom_growth": "Month-on-Month Shipment Growth",
    "eway_interstate_ratio": "Interstate Commerce Ratio",
    "eway_cancellation_rate": "E-Way Bill Cancellation Rate",
    "eway_avg_bill_value": "Average Shipment Value",
    "history_months_active": "Business Operating History (months)",
    "gst_filing_history_interaction": "GST Filing x Operating History",
    "upi_regularity_history_interaction": "UPI Regularity x Operating History",
    "overall_data_confidence": "Data History Completeness",
}

SHAP_REASON_TEMPLATES = {
    "gst_filing_rate": {
        "positive": "GST filed on time {pct}% of the time — strong compliance record (+{pts} pts)",
        "negative": "GST filing rate of {pct}% is below acceptable threshold (-{pts} pts)",
    },
    "gst_avg_delay_days": {
        "positive": "Average GST filing delay of only {val} days — well within limits (+{pts} pts)",
        "negative": "GST filings delayed by {val} days on average — indicates cash flow stress (-{pts} pts)",
    },
    "upi_round_amount_pct": {
        "positive": "UPI transactions show a natural value distribution — no round-amount clustering (+{pts} pts)",
        "negative": "{pct}% of UPI transactions are round amounts — potential synthetic transaction pattern (-{pts} pts)",
    },
    "upi_inflow_outflow_ratio": {
        "positive": "Healthy inflow-to-outflow ratio of {val}x — business is cash-flow positive (+{pts} pts)",
        "negative": "Inflow-to-outflow ratio of {val}x suggests more money going out than coming in (-{pts} pts)",
    },
    "history_months_active": {
        "positive": "Business has {months} months of verified transaction history — sufficient track record (+{pts} pts)",
        "negative": "Only {months} months of transaction history — limited data to assess creditworthiness (-{pts} pts)",
    },
    "overall_data_confidence": {
        "positive": "High data confidence ({pct}%) — score is based on complete signal coverage (+{pts} pts)",
        "negative": "Low data confidence ({pct}%) — sparse history reduces score reliability (-{pts} pts)",
    },
    "gst_filing_history_interaction": {
        "positive": "Strong GST compliance sustained over {months} months — reliability established (+{pts} pts)",
        "negative": "GST compliance record is too short to establish a reliable pattern (-{pts} pts)",
    },
    "upi_regularity_history_interaction": {
        "positive": "Consistent UPI transaction patterns across {months} months of history (+{pts} pts)",
        "negative": "UPI transaction patterns are not yet stable — insufficient history to trust regularity (-{pts} pts)",
    },
    "eway_cancellation_rate": {
        "positive": "E-way bill cancellation rate of {pct}% is within normal range (+{pts} pts)",
        "negative": "E-way bill cancellation rate of {pct}% suggests shipment irregularities (-{pts} pts)",
    },
    "upi_counterparty_diversity": {
        "positive": "{val} unique UPI counterparties — healthy diversity of business relationships (+{pts} pts)",
        "negative": "Only {val} unique UPI counterparties — high transaction concentration risk (-{pts} pts)",
    },
}


def get_risk_band(score: int) -> Dict[str, str]:
    for low, high, label, desc in RISK_BANDS:
        if low <= score <= high:
            return {"band": label, "description": desc, "range": f"{low}-{high}"}
    return {"band": "VERY_HIGH_RISK", "description": "Score out of range", "range": "300-499"}


def resolve_industry_profile(industry_code: str | None) -> Dict[str, Any]:
    if not industry_code:
        return {"code": None, **DEFAULT_INDUSTRY_PROFILE}

    normalized = "".join(ch for ch in industry_code if ch.isdigit())
    prefix = normalized[:2] if len(normalized) >= 2 else normalized
    profile = INDUSTRY_PROFILES.get(prefix, DEFAULT_INDUSTRY_PROFILE)
    return {
        "code": industry_code,
        "normalized_prefix": prefix or None,
        **profile,
    }


def _format_shap_reason(feature_name: str, shap_value: float, feature_value: float) -> str:
    display = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name.replace("_", " ").title())
    direction = "positively" if shap_value > 0 else "negatively"

    if "delay" in feature_name and shap_value < 0:
        return f"{display} of {feature_value:.0f} days is above acceptable threshold, reducing score"
    if "filing_rate" in feature_name and shap_value > 0:
        return f"Consistent {display} ({feature_value:.0%}) demonstrates compliance discipline"
    if "round_amount" in feature_name and shap_value < 0:
        return f"High {display} ({feature_value:.1f}%) suggests potential fund rotation"
    if "inflow_outflow" in feature_name:
        if shap_value > 0:
            return f"Healthy {display} of {feature_value:.2f}x indicates positive cash generation"
        return f"Weak {display} of {feature_value:.2f}x indicates cash outflow pressure"
    if "momentum" in feature_name and shap_value > 0:
        return f"Strong {display} (+{feature_value:.1f}%) shows growing business activity"
    if "cancellation" in feature_name and shap_value < 0:
        return f"Elevated {display} ({feature_value:.1f}%) flags potential operational issues"
    if "confidence" in feature_name:
        if shap_value < 0:
            return f"Limited trading history ({feature_value:.0%} confidence) lowers decision confidence"
        return f"Extensive trading history ({feature_value:.0%} confidence) supports reliable scoring"
    if "months_active" in feature_name:
        if shap_value < 0:
            return f"Short operating history ({feature_value:.0f} months) increases uncertainty for credit assessment"
        return f"Operating history of {feature_value:.0f} months improves confidence in repayment behavior"
    if "filing_history_interaction" in feature_name:
        if shap_value < 0:
            return f"Strong GST compliance is not yet backed by enough operating history to fully de-risk the borrower"
        return f"GST compliance sustained over a longer operating history materially improves confidence"
    if "regularity_history_interaction" in feature_name:
        if shap_value < 0:
            return f"Regular UPI behavior over a short operating history is treated cautiously"
        return f"Stable UPI cadence sustained over time improves repayment confidence"
    if "regularity" in feature_name and shap_value > 0:
        return f"Strong {display} ({feature_value:.0f}/100) shows predictable business patterns"
    if "e_invoice_velocity" in feature_name and shap_value > 0:
        return f"Active {display} ({feature_value:.0f}/month) confirms live business operations"
    if "diversity" in feature_name:
        if shap_value > 0:
            return f"Good {display} reduces concentration risk"
        return f"Low {display} indicates narrow customer and supplier diversity"

    return f"{display} ({feature_value:.2f}) impacts score {direction}"


def _to_display_number(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:.1f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _percent_value(feature_name: str, raw_value: float) -> float:
    if feature_name in {
        "gst_filing_rate",
        "overall_data_confidence",
    }:
        return raw_value * 100
    return raw_value


def _raw_value_summary(feature_name: str, raw_value: float, feature_vector: Dict[str, float]) -> str:
    months = int(round(feature_vector.get("history_months_active", 0)))
    if feature_name == "gst_filing_history_interaction":
        rate = feature_vector.get("gst_filing_rate", 0.0)
        return f"{rate:.2f} filing rate over {months} months"
    if feature_name == "upi_regularity_history_interaction":
        regularity = feature_vector.get("upi_regularity_score", 0.0)
        return f"{regularity:.0f}/100 regularity over {months} months"
    if feature_name in {"gst_filing_rate", "overall_data_confidence"}:
        return f"{raw_value * 100:.1f}%"
    if feature_name.endswith("_pct") or "ratio" not in feature_name and "cancellation_rate" in feature_name:
        return f"{raw_value:.1f}%"
    if feature_name == "history_months_active":
        return f"{months} months"
    if feature_name == "upi_inflow_outflow_ratio":
        return f"{raw_value:.2f}x"
    return _to_display_number(raw_value)


def _generate_reason_sentence(
    feature_name: str,
    shap_value: float,
    raw_value: float,
    feature_vector: Dict[str, float],
    score_points: int,
) -> str:
    direction = "positive" if shap_value > 0 else "negative"
    template = SHAP_REASON_TEMPLATES.get(feature_name, {}).get(direction)
    if template is None:
        display = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name.replace("_", " ").title())
        sign = "+" if shap_value > 0 else "-"
        return f"{display} influenced the score {'positively' if shap_value > 0 else 'negatively'} ({sign}{score_points} pts)"

    months = int(round(feature_vector.get("history_months_active", 0)))
    pct_value = round(_percent_value(feature_name, raw_value), 1)
    return template.format(
        val=_to_display_number(raw_value),
        pct=pct_value,
        pts=score_points,
        months=months,
    )


def _expected_value_to_probability(expected_value: Any) -> float:
    if isinstance(expected_value, (list, tuple, np.ndarray)):
        arr = np.array(expected_value, dtype=float).flatten()
        if arr.size == 0:
            return 0.5
        value = float(arr[-1])
    else:
        value = float(expected_value)

    if 0.0 <= value <= 1.0:
        return float(np.clip(value, 0.0, 1.0))
    return float(1.0 / (1.0 + np.exp(-value)))


def _map_probability_to_score(probability: float) -> int:
    clipped = float(np.clip(probability, 0.0, 1.0))
    centered = clipped * 2.0 - 1.0
    shaped = np.sign(centered) * (abs(centered) ** SCORE_CURVE_EXPONENT)
    scaled = 0.5 + 0.5 * shaped
    raw_score = int(round(300 + scaled * 600))
    return max(300, min(900, raw_score))


def _build_calibration_curve(y_true: np.ndarray, raw_probs: np.ndarray, calibrated_probs: np.ndarray) -> list[Dict[str, float]]:
    bins = np.linspace(0.0, 1.0, 11)
    points: list[Dict[str, float]] = []
    for start, end in zip(bins[:-1], bins[1:]):
        mask = (raw_probs >= start) & (raw_probs < end if end < 1.0 else raw_probs <= end)
        if not np.any(mask):
            continue
        points.append(
            {
                "bin_start": round(float(start), 2),
                "bin_end": round(float(end), 2),
                "sample_count": int(np.sum(mask)),
                "mean_raw_probability": round(float(np.mean(raw_probs[mask])), 4),
                "mean_calibrated_probability": round(float(np.mean(calibrated_probs[mask])), 4),
                "observed_repayment_rate": round(float(np.mean(y_true[mask])), 4),
            }
        )
    return points


def _build_calibration_trace(
    *,
    raw_probability: float,
    isotonic_probability: float,
    calibrated_probability: float,
    default_probability: float,
    method: str,
    curve_version: str,
    score_mapping: str,
    curve_points: list[Dict[str, float]] | None,
) -> Dict[str, Any]:
    return {
        "raw_probability": round(float(raw_probability), 4),
        "isotonic_probability": round(float(isotonic_probability), 4),
        "calibrated_probability": round(float(calibrated_probability), 4),
        "default_probability": round(float(default_probability), 4),
        "method": method,
        "curve_version": curve_version,
        "score_mapping": score_mapping,
        "tail_regularization_applied": calibrated_probability != isotonic_probability,
        "curve_points": curve_points or [],
    }


def _apply_maturity_umbrella_reason(
    *,
    all_shap: list[Dict[str, Any]],
    limit: int,
    months_active: int,
) -> list[Dict[str, Any]]:
    if months_active >= 6:
        return all_shap[:limit]

    leading = all_shap[:limit]
    interaction_items = [
        item for item in leading if item["feature_key"] in INTERACTION_REASON_KEYS
    ]
    interaction_negatives = [
        item for item in interaction_items if float(item["shap_value"]) < 0
    ]
    if len(interaction_items) < 2 or not interaction_negatives:
        return leading

    aggregate_impact = int(sum(item["score_impact"] for item in interaction_negatives))
    aggregate_shap = round(sum(float(item["shap_value"]) for item in interaction_negatives), 4)
    umbrella = {
        "feature": "Limited Operating History",
        "feature_key": "maturity_penalty_umbrella",
        "shap_value": aggregate_shap,
        "feature_value": float(months_active),
        "direction": "negative",
        "score_impact": aggregate_impact,
        "raw_value_display": (
            f"{months_active} months of verified history across GST and UPI behaviour signals"
        ),
        "reason": (
            f"Business has only {months_active} months of verified history — observed payment patterns "
            f"are too recent to establish reliable creditworthiness ({aggregate_impact} pts)"
        ),
        "supporting_features": [item["feature_key"] for item in interaction_negatives],
    }

    display_items = [umbrella]
    suppressed_keys = {item["feature_key"] for item in interaction_negatives}
    for item in all_shap:
        if item["feature_key"] in suppressed_keys:
            continue
        display_items.append(item)
        if len(display_items) >= limit:
            break
    return display_items


def _build_waterfall_rows(
    *,
    base_score: int,
    final_score: int,
    feature_shap_pairs: list[tuple[str, float, float]],
    features: Dict[str, float],
    limit: int = 5,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]], list[Dict[str, Any]]]:
    rows: list[Dict[str, Any]] = []
    top_reasons: list[Dict[str, Any]] = []
    all_shap: list[Dict[str, Any]] = []

    total_abs_shap = float(sum(abs(sval) for _, sval, _ in feature_shap_pairs))
    total_score_delta = int(final_score - base_score)
    total_abs_delta = abs(total_score_delta)
    impact_scale = (total_abs_delta / total_abs_shap) if total_abs_shap > 1e-6 else 0.0

    running_total = base_score

    for fname, sval, fval in feature_shap_pairs:
        shap_direction = 1 if float(sval) >= 0 else -1
        score_impact = int(round(abs(float(sval)) * impact_scale)) * shap_direction if impact_scale else 0
        direction = "positive" if shap_direction >= 0 else "negative"
        item = {
            "feature": FEATURE_DISPLAY_NAMES.get(fname, fname),
            "feature_key": fname,
            "shap_value": round(float(sval), 4),
            "feature_value": round(float(fval), 4),
            "direction": direction,
            "score_impact": score_impact,
            "raw_value_display": _raw_value_summary(fname, float(fval), features),
            "reason": _generate_reason_sentence(
                fname,
                float(sval),
                float(fval),
                features,
                abs(score_impact),
            ),
        }
        all_shap.append(item)

    display_items = _apply_maturity_umbrella_reason(
        all_shap=all_shap,
        limit=limit,
        months_active=int(round(features.get("history_months_active", 0))),
    )

    for item in display_items:
        start_score = running_total
        end_score = running_total + item["score_impact"]
        running_total = end_score
        top_reason = {
            **item,
            "start_score": start_score,
            "end_score": end_score,
            "running_total": end_score,
        }
        top_reasons.append(top_reason)
        rows.append(
            {
                "label": top_reason["reason"],
                "feature_key": top_reason["feature_key"],
                "direction": top_reason["direction"],
                "score_impact": top_reason["score_impact"],
                "start_score": start_score,
                "end_score": end_score,
                "running_total": end_score,
                "raw_value_display": top_reason["raw_value_display"],
                "reason": top_reason["reason"],
                "kind": "reason",
            }
        )

    residual = int(final_score - running_total)
    if residual != 0:
        residual_direction = "positive" if residual >= 0 else "negative"
        residual_end = running_total + residual
        rows.append(
            {
                "label": "Other model factors across the remaining signals",
                "feature_key": "other_model_factors",
                "direction": residual_direction,
                "score_impact": residual,
                "start_score": running_total,
                "end_score": residual_end,
                "running_total": residual_end,
                "raw_value_display": "Remaining SHAP factors outside the top 5 reasons",
                "reason": "Other model factors across the remaining signals",
                "kind": "other",
            }
        )
        running_total = residual_end

    rows.insert(
        0,
        {
            "label": "Base score (population average before business-specific signals)",
            "feature_key": "base_score",
            "direction": "neutral",
            "score_impact": 0,
            "start_score": base_score,
            "end_score": base_score,
            "running_total": base_score,
            "raw_value_display": "Model expected value across training businesses",
            "reason": "Base score (population average before business-specific signals)",
            "kind": "base",
        },
    )
    rows.append(
        {
            "label": "Final credit score",
            "feature_key": "final_score",
            "direction": "neutral",
            "score_impact": 0,
            "start_score": final_score,
            "end_score": final_score,
            "running_total": final_score,
            "raw_value_display": "300-900 calibrated final score",
            "reason": "Final credit score",
            "kind": "final",
        }
    )

    return top_reasons, all_shap, rows


def recommend_loan(
    score: int,
    monthly_revenue: float = 0,
    fraud_risk: str = "LOW",
    *,
    industry_code: str | None = None,
    data_confidence: float = 1.0,
    months_active: float = 12.0,
) -> Dict[str, Any]:
    industry_profile = resolve_industry_profile(industry_code)
    confidence = float(np.clip(data_confidence, 0.3, 1.0))
    confidence_multiplier = round(0.55 + 0.45 * confidence, 3)
    maturity_multiplier = round(0.7 + 0.3 * min(max(months_active, 3.0), 24.0) / 24.0, 3)

    if fraud_risk == "HIGH":
        return {
            "eligible": False,
            "reason": "High fraud risk blocks credit recommendation pending investigation",
            "recommended_amount": 0,
            "recommended_tenure_months": 0,
            "tenure_options_months": [],
            "indicative_rate_pct": None,
            "base_rate": 8.5,
            "risk_premium": None,
            "industry_profile": industry_profile,
            "confidence_multiplier": confidence_multiplier,
            "recommendation_basis": "Recommendation blocked because fraud risk is high despite revenue and industry profile inputs.",
        }

    if score < 500:
        return {
            "eligible": False,
            "reason": "Score below minimum threshold (500) for MSME lending",
            "recommended_amount": 0,
            "recommended_tenure_months": 0,
            "tenure_options_months": [],
            "indicative_rate_pct": None,
            "base_rate": 8.5,
            "risk_premium": None,
            "industry_profile": industry_profile,
            "confidence_multiplier": confidence_multiplier,
            "recommendation_basis": "Recommendation blocked because the calibrated score is below the minimum policy threshold.",
        }

    multiplier = {
        (500, 599): 2.0,
        (600, 699): 3.5,
        (700, 799): 5.0,
        (800, 900): 6.0,
    }
    for (lo, hi), mult in multiplier.items():
        if lo <= score <= hi:
            max_amount = monthly_revenue * mult
            break
    else:
        max_amount = monthly_revenue * 2.0

    industry_multiplier = float(industry_profile["amount_multiplier"])
    max_amount *= industry_multiplier
    max_amount *= confidence_multiplier
    max_amount *= maturity_multiplier

    if fraud_risk == "MEDIUM":
        max_amount *= 0.65

    base_rate = 8.5
    risk_premium = max(0, (800 - score) / 100 * 1.5)
    if fraud_risk == "MEDIUM":
        risk_premium += 1.0
    rate = round(base_rate + risk_premium, 2)

    profile_tenures = industry_profile["tenure_options_months"]
    if score >= 750 and fraud_risk == "LOW":
        base_tenure = 60
    elif score >= 650:
        base_tenure = 36
    else:
        base_tenure = 12
    tenure = min(profile_tenures, key=lambda option: abs(option - base_tenure))

    revenue_basis = abs(monthly_revenue)
    recommendation_basis = (
        f"Based on verified monthly business inflow of approximately INR {round(revenue_basis):,}, "
        f"adjusted for the {industry_profile['basis_phrase']}, with a "
        f"{'conservative' if confidence < 0.7 else 'standard'} multiplier applied because data confidence is "
        f"{round(confidence * 100)}% across {int(round(months_active))} months of history."
    )

    return {
        "eligible": True,
        "recommended_amount": round(max(100000, max_amount), -3),
        "recommended_tenure_months": tenure,
        "tenure_options_months": profile_tenures,
        "indicative_rate_pct": rate,
        "base_rate": base_rate,
        "risk_premium": round(risk_premium, 2),
        "industry_profile": industry_profile,
        "industry_multiplier": industry_multiplier,
        "confidence_multiplier": confidence_multiplier,
        "maturity_multiplier": maturity_multiplier,
        "repayment_structure": industry_profile["repayment_structure"],
        "recommendation_basis": recommendation_basis,
    }


class MSMECreditScorer:
    def __init__(self) -> None:
        self.model = None
        self.explainer = None
        self.calibrator = None
        self.backend = "heuristic"
        self.model_version = "fallback-heuristic-v1.0"
        self.model_metrics: Dict[str, Any] = {}
        self.model_artifact_path: str | None = None
        self.metadata_artifact_path: str | None = None
        self.calibration_artifact_path: str | None = None
        self.calibration_curve_artifact_path: str | None = None
        self.population_base_score: int | None = None
        self.calibration_method = "identity"
        self.score_mapping = "linear_300_900"
        self.last_loaded_at: str | None = None
        self._load_or_train()

    def _artifact_paths(self) -> Dict[str, Path]:
        base_dir = Path(get_settings().model_artifact_dir)
        base_dir.mkdir(parents=True, exist_ok=True)
        return {
            "xgb": base_dir / "msme_credit_xgb.json",
            "sklearn": base_dir / "msme_credit_sklearn.pkl",
            "calibrator": base_dir / "msme_credit_calibrator.pkl",
            "calibration_curve": base_dir / "msme_credit_calibration_curve.json",
            "metadata": base_dir / "msme_credit_model_metadata.json",
        }

    @staticmethod
    def _sigmoid(value: np.ndarray | float) -> np.ndarray | float:
        return 1.0 / (1.0 + np.exp(-value))

    def _split_dataset(
        self,
        X: np.ndarray,
        y: np.ndarray,
        group_ids: np.ndarray,
        dataset_meta: Dict[str, Any],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if GroupShuffleSplit is not None:
            outer = GroupShuffleSplit(n_splits=1, test_size=0.15, random_state=42)
            train_cal_idx, test_idx = next(outer.split(X, y, groups=group_ids))
            inner = GroupShuffleSplit(n_splits=1, test_size=0.1765, random_state=43)
            train_rel, cal_rel = next(
                inner.split(X[train_cal_idx], y[train_cal_idx], groups=group_ids[train_cal_idx])
            )
            train_idx = train_cal_idx[train_rel]
            cal_idx = train_cal_idx[cal_rel]
            dataset_meta["split_strategy"] = "group_shuffle_split_train_cal_test_by_business"
        elif train_test_split is not None:
            train_cal_idx, test_idx = train_test_split(
                np.arange(len(y)),
                test_size=0.15,
                random_state=42,
                stratify=y,
            )
            cal_size = max(1, int(round(len(train_cal_idx) * 0.1765)))
            train_idx, cal_idx = train_test_split(
                train_cal_idx,
                test_size=cal_size,
                random_state=43,
                stratify=y[train_cal_idx],
            )
            dataset_meta["split_strategy"] = "row_level_train_cal_test_split"
        else:
            test_cut = max(1, int(len(y) * 0.15))
            cal_cut = max(1, int(len(y) * 0.15))
            train_idx = np.arange(0, len(y) - test_cut - cal_cut)
            cal_idx = np.arange(len(y) - test_cut - cal_cut, len(y) - test_cut)
            test_idx = np.arange(len(y) - test_cut, len(y))
            dataset_meta["split_strategy"] = "tail_train_cal_test_fallback"

        dataset_meta["split_counts"] = {
            "train": int(len(train_idx)),
            "calibration": int(len(cal_idx)),
            "test": int(len(test_idx)),
        }
        return (
            X[train_idx],
            X[cal_idx],
            X[test_idx],
            y[train_idx],
            y[cal_idx],
            y[test_idx],
        )

    def _apply_calibration(self, probability: float) -> float:
        _, calibrated = self._calibration_details(probability)
        return calibrated

    def _calibration_details(self, probability: float) -> tuple[float, float]:
        clipped = float(np.clip(probability, 0.0, 1.0))
        if self.calibrator is None:
            return clipped, clipped
        isotonic = float(self.calibrator.predict([clipped])[0])
        isotonic = float(np.clip(isotonic, 0.0, 1.0))
        if isotonic <= TAIL_SHRINK_THRESHOLD:
            return isotonic, isotonic
        shrunk = TAIL_SHRINK_THRESHOLD + (isotonic - TAIL_SHRINK_THRESHOLD) * TAIL_SHRINK_FACTOR
        final_probability = float(np.clip(min(shrunk, TAIL_SHRINK_CAP), 0.0, 1.0))
        return isotonic, final_probability

    def _prepare_real_outcome_dataset(
        self,
        real_outcomes: list[Dict[str, Any]] | None,
    ) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None, Dict[str, Any]]:
        if not real_outcomes:
            return None, None, None, {
                "real_sample_count": 0,
                "real_positive_rate": None,
                "real_outcome_threshold_met": False,
            }

        rows: list[list[float]] = []
        labels: list[int] = []
        groups: list[int] = []
        valid_records = 0
        for idx, outcome in enumerate(real_outcomes):
            feature_snapshot = outcome.get("feature_snapshot") or {}
            if any(name not in feature_snapshot for name in FEATURE_NAMES):
                continue
            rows.append([float(feature_snapshot.get(name, 0.0)) for name in FEATURE_NAMES])
            labels.append(1 if outcome.get("repaid") else 0)
            groups.append(100000 + idx)
            valid_records += 1

        if not rows:
            return None, None, None, {
                "real_sample_count": 0,
                "real_positive_rate": None,
                "real_outcome_threshold_met": False,
            }

        y_real = np.array(labels, dtype=int)
        return (
            np.array(rows, dtype=float),
            y_real,
            np.array(groups, dtype=int),
            {
                "real_sample_count": valid_records,
                "real_positive_rate": round(float(np.mean(y_real)), 4),
                "real_outcome_threshold_met": valid_records >= REAL_OUTCOME_MIN_RECORDS,
            },
        )

    def _generate_synthetic_dataset(
        self,
        seed: int = 42,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
        rng = np.random.default_rng(seed)
        feature_index = {name: i for i, name in enumerate(FEATURE_NAMES)}
        rows: list[list[float]] = []
        labels: list[int] = []
        groups: list[int] = []
        archetype_counts = {
            "healthy_grower": 0,
            "struggling_honest": 0,
            "fraudulent": 0,
        }
        event_counters = {
            "missed_filing": 0,
            "delayed_payment": 0,
            "circular_fund_rotation": 0,
            "shipment_stall": 0,
            "default_in_3m": 0,
        }
        total_month_observations = 0

        n_businesses = 1800
        label_horizon_months = 3

        for business_id in range(n_businesses):
            archetype = rng.choice(
                ["healthy_grower", "struggling_honest", "fraudulent"],
                p=[0.70, 0.20, 0.10],
            )
            archetype_counts[archetype] += 1

            if archetype == "healthy_grower":
                total_months = int(rng.integers(15, 31))
            elif archetype == "struggling_honest":
                total_months = int(rng.integers(12, 25))
            else:
                total_months = int(rng.integers(8, 19))

            management_quality = float(np.clip(rng.normal(0.6 if archetype == "healthy_grower" else -0.1, 0.8), -2, 2))
            market_tailwind = float(np.clip(rng.normal(0.3 if archetype == "healthy_grower" else -0.2, 0.9), -2, 2))
            capital_buffer = float(np.clip(rng.normal(0.5 if archetype == "healthy_grower" else -0.15, 0.8), -2, 2))
            fraud_propensity = float(
                np.clip(
                    rng.normal(
                        1.25 if archetype == "fraudulent" else (0.35 if archetype == "struggling_honest" else -0.55),
                        0.5,
                    ),
                    -1.5,
                    2.5,
                )
            )

            monthly_features: list[Dict[str, float]] = []
            default_events: list[int] = []
            prev_missed = 0
            prev_delayed = 0
            prev_rotation = 0
            prev_stall = 0
            repayment_stress = 0.0

            for month_idx in range(total_months):
                total_month_observations += 1
                months_active = float(month_idx + 1)
                young_factor = max(0.0, (12.0 - months_active) / 12.0)
                hidden_shock = float(rng.normal(0.0, 0.75))
                compliance_shock = float(rng.normal(0.0, 0.45))
                demand_shock = float(rng.normal(0.0, 0.55))

                if archetype == "healthy_grower":
                    gst_filing_rate = rng.beta(18, 1.5)
                    gst_avg_delay_days = rng.normal(2.5, 1.2)
                    upi_regularity_score = rng.normal(84, 6)
                    upi_round_amount_pct = rng.normal(8, 3)
                    upi_inflow_outflow_ratio = rng.normal(1.15, 0.12)
                    eway_cancellation_rate = rng.normal(2.2, 1.0)
                elif archetype == "struggling_honest":
                    gst_filing_rate = rng.beta(8, 3.5)
                    gst_avg_delay_days = rng.normal(8.5, 3.0)
                    upi_regularity_score = rng.normal(63, 8)
                    upi_round_amount_pct = rng.normal(15, 4)
                    upi_inflow_outflow_ratio = rng.normal(0.92, 0.14)
                    eway_cancellation_rate = rng.normal(5.8, 1.8)
                else:
                    gst_filing_rate = rng.beta(5, 4.5)
                    gst_avg_delay_days = rng.normal(11.5, 4.0)
                    upi_regularity_score = rng.normal(55, 10)
                    upi_round_amount_pct = rng.normal(29, 7)
                    upi_inflow_outflow_ratio = rng.normal(0.82, 0.16)
                    eway_cancellation_rate = rng.normal(8.2, 2.4)

                gst_filing_rate = float(np.clip(
                    gst_filing_rate
                    - 0.03 * max(-market_tailwind, 0)
                    - 0.025 * max(repayment_stress, 0)
                    + 0.01 * compliance_shock,
                    0.35,
                    1.0,
                ))
                gst_avg_delay_days = float(np.clip(
                    gst_avg_delay_days
                    + 1.2 * max(-management_quality, 0)
                    + 0.8 * max(repayment_stress, 0)
                    - 0.4 * market_tailwind
                    + 1.1 * max(-compliance_shock, 0),
                    0,
                    30,
                ))
                gst_on_time_pct = float(np.clip(
                    38 + 62 * gst_filing_rate - 1.15 * gst_avg_delay_days + rng.normal(0, 3.5),
                    20,
                    100,
                ))
                gst_e_invoice_velocity = float(np.clip(
                    6
                    + 1.15 * months_active
                    + 28 * gst_filing_rate
                    + 10 * max(market_tailwind + demand_shock, -1)
                    - 6 * max(repayment_stress, 0),
                    5,
                    240,
                ))
                gst_e_invoice_trend = float(
                    1.0 if demand_shock + market_tailwind > -0.15 else -1.0
                )
                gst_itc_variance_avg = float(np.clip(
                    3.5
                    + 4.5 * max(repayment_stress, 0)
                    + 5.5 * max(fraud_propensity, 0)
                    + 1.8 * max(-market_tailwind, 0)
                    + rng.normal(0, 1.1),
                    0,
                    30,
                ))
                gst_itc_variance_trend = float(np.clip(
                    rng.normal(0.02, 0.10)
                    + 0.16 * max(repayment_stress, 0)
                    + 0.12 * max(fraud_propensity, 0),
                    -0.5,
                    0.8,
                ))

                upi_avg_daily_txns = float(np.clip(
                    4
                    + 0.52 * months_active
                    + 0.08 * gst_e_invoice_velocity
                    + 3.0 * market_tailwind
                    - 1.8 * max(repayment_stress, 0)
                    + rng.normal(0, 2.0),
                    1,
                    65,
                ))
                upi_regularity_score = float(np.clip(
                    upi_regularity_score
                    + 4.0 * management_quality
                    - 7.0 * max(repayment_stress, 0)
                    + 2.5 * market_tailwind
                    + rng.normal(0, 4.0),
                    20,
                    100,
                ))
                upi_inflow_outflow_ratio = float(np.clip(
                    upi_inflow_outflow_ratio
                    + 0.08 * capital_buffer
                    - 0.12 * max(repayment_stress, 0)
                    + 0.07 * market_tailwind
                    + rng.normal(0, 0.06),
                    0.3,
                    2.5,
                ))
                upi_round_amount_pct = float(np.clip(
                    upi_round_amount_pct
                    + 4.5 * max(fraud_propensity, 0)
                    + 2.0 * max(repayment_stress, 0)
                    + rng.normal(0, 2.0),
                    1,
                    65,
                ))
                upi_net_cash_flow = float(np.clip(
                    120000
                    + 45000 * months_active
                    + 5200 * gst_e_invoice_velocity
                    + 90000 * market_tailwind
                    + 70000 * capital_buffer
                    - 160000 * max(repayment_stress, 0)
                    + rng.normal(0, 60000),
                    -500000,
                    2500000,
                ))
                upi_counterparty_diversity = float(np.clip(
                    0.8
                    + 0.06 * months_active
                    + 0.02 * upi_avg_daily_txns
                    - 0.25 * max(fraud_propensity, 0)
                    + rng.normal(0, 0.15),
                    0.4,
                    5.0,
                ))
                upi_volume_growth = float(np.clip(
                    8.0 * market_tailwind
                    + 0.16 * gst_e_invoice_velocity
                    - 9.0 * max(repayment_stress, 0)
                    + rng.normal(0, 4.5),
                    -45,
                    60,
                ))

                eway_avg_monthly_bills = float(np.clip(
                    5
                    + 0.85 * months_active
                    + 0.20 * gst_e_invoice_velocity
                    + 2.0 * market_tailwind
                    - 2.2 * max(repayment_stress, 0)
                    + rng.normal(0, 2.5),
                    3,
                    140,
                ))
                eway_volume_momentum = float(np.clip(
                    7.0 * market_tailwind
                    + 0.40 * upi_volume_growth
                    - 12.0 * max(repayment_stress, 0)
                    + rng.normal(0, 5.0),
                    -50,
                    60,
                ))
                eway_mom_growth = float(np.clip(
                    0.35 * eway_volume_momentum + rng.normal(0, 2.5),
                    -25,
                    25,
                ))
                eway_interstate_ratio = float(np.clip(
                    32
                    + 0.45 * months_active
                    + 6.0 * market_tailwind
                    - 2.0 * max(fraud_propensity, 0)
                    + rng.normal(0, 4.5),
                    5,
                    90,
                ))
                eway_cancellation_rate = float(np.clip(
                    eway_cancellation_rate
                    + 2.5 * max(repayment_stress, 0)
                    + 1.0 * max(fraud_propensity, 0)
                    + rng.normal(0, 0.9),
                    0,
                    25,
                ))
                eway_avg_bill_value = float(np.clip(
                    90000
                    + 0.12 * max(upi_net_cash_flow, 0)
                    + 70000 * market_tailwind
                    - 50000 * max(repayment_stress, 0)
                    + rng.normal(0, 35000),
                    50000,
                    1200000,
                ))

                overall_data_confidence = float(
                    np.clip(0.3 + 0.7 * min(months_active, 12.0) / 12.0, 0.3, 1.0)
                )
                gst_history_support = gst_filing_rate * months_active
                upi_history_support = upi_regularity_score * months_active

                monthly_features.append(
                    {
                        "gst_filing_rate": gst_filing_rate,
                        "gst_avg_delay_days": gst_avg_delay_days,
                        "gst_on_time_pct": gst_on_time_pct,
                        "gst_e_invoice_velocity": gst_e_invoice_velocity,
                        "gst_e_invoice_trend": gst_e_invoice_trend,
                        "gst_itc_variance_avg": gst_itc_variance_avg,
                        "gst_itc_variance_trend": gst_itc_variance_trend,
                        "upi_avg_daily_txns": upi_avg_daily_txns,
                        "upi_regularity_score": upi_regularity_score,
                        "upi_inflow_outflow_ratio": upi_inflow_outflow_ratio,
                        "upi_round_amount_pct": upi_round_amount_pct,
                        "upi_net_cash_flow": upi_net_cash_flow,
                        "upi_counterparty_diversity": upi_counterparty_diversity,
                        "upi_volume_growth": upi_volume_growth,
                        "eway_avg_monthly_bills": eway_avg_monthly_bills,
                        "eway_volume_momentum": eway_volume_momentum,
                        "eway_mom_growth": eway_mom_growth,
                        "eway_interstate_ratio": eway_interstate_ratio,
                        "eway_cancellation_rate": eway_cancellation_rate,
                        "eway_avg_bill_value": eway_avg_bill_value,
                        "history_months_active": months_active,
                        "gst_filing_history_interaction": gst_history_support,
                        "upi_regularity_history_interaction": upi_history_support,
                        "overall_data_confidence": overall_data_confidence,
                    }
                )

                missed_filing_prob = float(
                    self._sigmoid(
                        -2.6
                        + 4.4 * (1 - gst_filing_rate)
                        + 0.09 * gst_avg_delay_days
                        + 0.45 * (gst_itc_variance_trend > 0.14)
                        + 0.40 * young_factor
                        - 0.30 * management_quality
                        + 0.25 * max(-market_tailwind, 0)
                        + 0.20 * max(-compliance_shock, 0)
                    )
                )
                missed_filing = int(rng.binomial(1, missed_filing_prob))

                delayed_payment_prob = float(
                    self._sigmoid(
                        -2.75
                        + 1.45 * prev_missed
                        + 0.90 * (upi_inflow_outflow_ratio < 0.95)
                        + 0.45 * (upi_net_cash_flow < 100000)
                        + 0.40 * max(repayment_stress, 0)
                        + 0.35 * young_factor
                        + 0.45 * max(-capital_buffer, 0)
                        + 0.25 * hidden_shock
                    )
                )
                delayed_payment = int(rng.binomial(1, delayed_payment_prob))

                circular_fund_rotation_prob = float(
                    self._sigmoid(
                        -3.35
                        + 0.10 * upi_round_amount_pct
                        + 0.85 * (upi_counterparty_diversity < 1.15)
                        + 0.95 * max(fraud_propensity, 0)
                        + 0.40 * (upi_inflow_outflow_ratio < 0.82)
                        + 0.25 * prev_rotation
                        + 0.25 * hidden_shock
                    )
                )
                circular_fund_rotation = int(rng.binomial(1, circular_fund_rotation_prob))

                shipment_stall_prob = float(
                    self._sigmoid(
                        -2.7
                        + 0.85 * (eway_volume_momentum < -10)
                        + 0.08 * eway_cancellation_rate
                        + 0.62 * prev_delayed
                        + 0.30 * max(repayment_stress, 0)
                        + 0.35 * max(-market_tailwind, 0)
                        + 0.16 * hidden_shock
                    )
                )
                shipment_stall = int(rng.binomial(1, shipment_stall_prob))

                if month_idx < label_horizon_months:
                    default_event = 0
                else:
                    if months_active <= 3.0:
                        age_penalty = float(rng.normal(2.35, 0.35))
                    elif months_active <= 6.0:
                        age_penalty = float(rng.normal(1.15, 0.3))
                    elif months_active <= 12.0:
                        age_penalty = float(rng.normal(0.45, 0.2))
                    else:
                        age_penalty = float(rng.normal(0.0, 0.1))

                    default_hazard = float(
                        self._sigmoid(
                            -5.55
                            + (0.82 if archetype == "healthy_grower" else (0.55 if archetype == "struggling_honest" else 0.95))
                            + 1.05 * prev_delayed
                            + 1.28 * prev_rotation
                            + 0.82 * shipment_stall
                            + 0.78 * young_factor
                            + 1.10 * (gst_history_support < 8.0)
                            + 0.80 * (upi_history_support < 720.0)
                            + 2.20 * (overall_data_confidence < 0.5)
                            + 3.00 * max(0.85 - overall_data_confidence, 0.0)
                            + 0.50 * (gst_itc_variance_avg > 10.5)
                            + 0.46 * (upi_regularity_score < 58.0)
                            + 0.40 * max(-capital_buffer, 0)
                            + age_penalty
                            + 0.24 * hidden_shock
                        )
                    )
                    default_event = int(rng.binomial(1, default_hazard))

                event_counters["missed_filing"] += missed_filing
                event_counters["delayed_payment"] += delayed_payment
                event_counters["circular_fund_rotation"] += circular_fund_rotation
                event_counters["shipment_stall"] += shipment_stall
                event_counters["default_in_3m"] += default_event
                default_events.append(default_event)

                repayment_stress = float(
                    np.clip(
                        0.45 * repayment_stress
                        + 0.15 * missed_filing
                        + 0.28 * delayed_payment
                        + 0.22 * shipment_stall
                        + 0.14 * circular_fund_rotation
                        + 0.10 * max(-market_tailwind, 0)
                        - 0.08 * max(capital_buffer, 0),
                        0.0,
                        2.5,
                    )
                )
                prev_missed = missed_filing
                prev_delayed = delayed_payment
                prev_rotation = circular_fund_rotation
                prev_stall = shipment_stall

                if default_event:
                    break

            if len(monthly_features) <= label_horizon_months:
                continue

            max_row_idx = len(monthly_features) - label_horizon_months
            for row_idx in range(max_row_idx):
                future_window = default_events[row_idx + 1 : row_idx + 1 + label_horizon_months]
                label = 0 if any(future_window) else 1
                row_vector = [monthly_features[row_idx].get(name, 0.0) for name in FEATURE_NAMES]
                rows.append(row_vector)
                labels.append(label)
                groups.append(business_id)

        X = np.array(rows, dtype=float)
        y = np.array(labels, dtype=int)
        group_ids = np.array(groups, dtype=int)

        dataset_meta = {
            "generation_method": "event_driven_panel_v12",
            "label_target": "loan_stays_current_over_next_3_months",
            "label_horizon_months": label_horizon_months,
            "panel_rows": int(len(y)),
            "synthetic_businesses": n_businesses,
            "archetype_distribution": {
                key: round(value / n_businesses, 4) for key, value in archetype_counts.items()
            },
            "event_rates": {
                key: round(value / max(total_month_observations, 1), 4) for key, value in event_counters.items()
            },
            "non_linear_interactions": [
                "gst_filing_rate x history_months_active",
                "upi_regularity_score x history_months_active",
                "delayed_payment_event x shipment_stall_event",
            ],
            "noise_terms": ["hidden_shock", "management_quality", "market_tailwind", "capital_buffer", "age_penalty"],
            "inference_feature_count": len(FEATURE_NAMES),
            "hidden_variables_exposed_to_model": False,
            "calibration_target": "repayment_probability",
            "feature_schema_version": TRAINING_SCHEMA_ID,
        }
        return X, y, group_ids, dataset_meta

    def _compute_metrics(
        self,
        y_true: np.ndarray,
        raw_probs: np.ndarray,
        calibrated_probs: np.ndarray,
        dataset_meta: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if accuracy_score is None:
            return {}
        preds = (calibrated_probs >= 0.5).astype(int)
        metrics = {
            "accuracy": round(float(accuracy_score(y_true, preds)), 4),
            "auc": round(float(roc_auc_score(y_true, calibrated_probs)), 4),
            "precision": round(float(precision_score(y_true, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, preds, zero_division=0)), 4),
            "positive_rate": round(float(np.mean(y_true)), 4),
            "train_distribution": {
                "features": len(FEATURE_NAMES),
                "samples": int(len(y_true)),
            },
            "raw_model_auc": round(float(roc_auc_score(y_true, raw_probs)), 4),
            "raw_model_brier": round(float(brier_score_loss(y_true, raw_probs)), 4),
            "calibrated_brier": round(float(brier_score_loss(y_true, calibrated_probs)), 4),
            "calibration_method": self.calibration_method,
            "score_mapping": self.score_mapping,
            "calibration_curve": _build_calibration_curve(y_true, raw_probs, calibrated_probs),
            "feature_schema_version": TRAINING_SCHEMA_ID,
        }
        if dataset_meta:
            metrics["synthetic_dataset"] = dataset_meta
        return metrics

    def _save_artifacts(self) -> None:
        paths = self._artifact_paths()
        metadata = {
            "model_version": self.model_version,
            "backend": self.backend,
            "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "feature_names": FEATURE_NAMES,
            "training_schema_id": TRAINING_SCHEMA_ID,
            "model_metrics": self.model_metrics,
            "calibration_method": self.calibration_method,
            "score_mapping": self.score_mapping,
            "calibration_curve_path": None,
            "population_base_score": self.population_base_score,
        }

        if self.backend == "xgboost" and self.model is not None:
            self.model.save_model(paths["xgb"])
            metadata["model_artifact_path"] = str(paths["xgb"])
        elif self.backend == "sklearn_gbm" and self.model is not None:
            with paths["sklearn"].open("wb") as handle:
                pickle.dump(self.model, handle)
            metadata["model_artifact_path"] = str(paths["sklearn"])
        else:
            metadata["model_artifact_path"] = None

        if self.calibrator is not None:
            with paths["calibrator"].open("wb") as handle:
                pickle.dump(self.calibrator, handle)
            metadata["calibration_artifact_path"] = str(paths["calibrator"])
        else:
            metadata["calibration_artifact_path"] = None

        calibration_curve_payload = {
            "model_version": self.model_version,
            "method": self.calibration_method,
            "score_mapping": self.score_mapping,
            "curve_points": self.model_metrics.get("calibration_curve", []),
        }
        with paths["calibration_curve"].open("w", encoding="utf-8") as handle:
            json.dump(calibration_curve_payload, handle, indent=2)
        metadata["calibration_curve_path"] = str(paths["calibration_curve"])

        with paths["metadata"].open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)

        self.model_artifact_path = metadata["model_artifact_path"]
        self.metadata_artifact_path = str(paths["metadata"])
        self.calibration_artifact_path = metadata["calibration_artifact_path"]
        self.calibration_curve_artifact_path = metadata["calibration_curve_path"]
        self.population_base_score = metadata.get("population_base_score")

    def _load_from_artifacts(self) -> bool:
        paths = self._artifact_paths()
        if not paths["metadata"].exists():
            return False

        with paths["metadata"].open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)

        if metadata.get("feature_names") != FEATURE_NAMES:
            return False
        if metadata.get("training_schema_id") != TRAINING_SCHEMA_ID:
            return False

        backend = metadata.get("backend")
        if backend == "xgboost" and HAS_XGB and paths["xgb"].exists():
            model = xgb.Booster()
            model.load_model(str(paths["xgb"]))
            self.model = model
            self.explainer = shap.TreeExplainer(model) if shap is not None else None
        elif backend == "sklearn_gbm" and HAS_SKLEARN_GBM and paths["sklearn"].exists():
            with paths["sklearn"].open("rb") as handle:
                self.model = pickle.load(handle)
            self.explainer = shap.TreeExplainer(self.model) if shap is not None else None
        else:
            return False

        calibration_artifact_path = metadata.get("calibration_artifact_path")
        if calibration_artifact_path:
            if not paths["calibrator"].exists():
                return False
            with paths["calibrator"].open("rb") as handle:
                self.calibrator = pickle.load(handle)
        else:
            self.calibrator = None

        self.backend = backend
        self.model_version = metadata.get(
            "model_version",
            "xgb-msme-v12.0" if backend == "xgboost" else "sklearn-gbm-msme-v12.0",
        )
        self.model_metrics = metadata.get("model_metrics", {})
        self.model_artifact_path = metadata.get("model_artifact_path")
        self.metadata_artifact_path = str(paths["metadata"])
        self.calibration_artifact_path = calibration_artifact_path
        self.calibration_curve_artifact_path = metadata.get("calibration_curve_path")
        self.population_base_score = metadata.get("population_base_score")
        self.calibration_method = metadata.get("calibration_method", "identity")
        self.score_mapping = metadata.get("score_mapping", "linear_300_900")
        self.last_loaded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return True

    def _train_model(self, real_outcomes: list[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        if not HAS_SKLEARN_GBM and not HAS_XGB:
            self.model = None
            self.explainer = None
            self.calibrator = None
            self.backend = "heuristic"
            self.model_version = "fallback-heuristic-v1.0"
            self.model_metrics = {}
            self.calibration_method = "identity"
            self.score_mapping = "linear_300_900"
            self.calibration_curve_artifact_path = None
            self.population_base_score = 600
            self.last_loaded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return {
                "training_sample_size": 0,
                "synthetic_sample_count": 0,
                "real_sample_count": 0,
                "real_label_ratio": 0.0,
                "feature_schema_version": TRAINING_SCHEMA_ID,
            }

        X_syn, y_syn, group_ids_syn, dataset_meta = self._generate_synthetic_dataset()
        X = X_syn
        y = y_syn
        group_ids = group_ids_syn
        real_X, real_y, real_groups, real_meta = self._prepare_real_outcome_dataset(real_outcomes)
        synthetic_sample_count = int(len(y_syn))
        real_sample_count = int(real_meta["real_sample_count"])
        use_real_outcomes = real_X is not None and real_sample_count >= REAL_OUTCOME_MIN_RECORDS
        if use_real_outcomes:
            X = np.vstack([X_syn, real_X])
            y = np.concatenate([y_syn, real_y])
            group_ids = np.concatenate([group_ids_syn, real_groups])

        dataset_meta["real_outcomes"] = {
            **real_meta,
            "used_for_training": use_real_outcomes,
            "minimum_required": REAL_OUTCOME_MIN_RECORDS,
        }
        X_train, X_cal, X_test, y_train, y_cal, y_test = self._split_dataset(X, y, group_ids, dataset_meta)

        version_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        if HAS_XGB:
            dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURE_NAMES)
            dcal = xgb.DMatrix(X_cal, label=y_cal, feature_names=FEATURE_NAMES)
            dtest = xgb.DMatrix(X_test, label=y_test, feature_names=FEATURE_NAMES)
            params = {
                "max_depth": 4,
                "eta": 0.1,
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "seed": 42,
            }
            self.model = xgb.train(params, dtrain, num_boost_round=100)
            raw_cal_probs = self.model.predict(dcal)
            raw_test_probs = self.model.predict(dtest)
            self.explainer = shap.TreeExplainer(self.model) if shap is not None else None
            self.backend = "xgboost"
            self.model_version = f"xgb-msme-v12.0-{version_stamp}"
        else:
            self.model = GradientBoostingClassifier(
                n_estimators=180,
                learning_rate=0.05,
                max_depth=3,
                random_state=42,
            )
            self.model.fit(X_train, y_train)
            raw_cal_probs = self.model.predict_proba(X_cal)[:, 1]
            raw_test_probs = self.model.predict_proba(X_test)[:, 1]
            self.explainer = shap.TreeExplainer(self.model) if shap is not None else None
            self.backend = "sklearn_gbm"
            self.model_version = f"sklearn-gbm-msme-v12.0-{version_stamp}"

        if IsotonicRegression is not None and len(np.unique(y_cal)) > 1:
            self.calibrator = IsotonicRegression(out_of_bounds="clip")
            self.calibrator.fit(raw_cal_probs, y_cal)
            self.calibration_method = "isotonic_regression_tail_regularized"
        else:
            self.calibrator = None
            self.calibration_method = "identity"

        self.score_mapping = f"non_linear_power_curve_{SCORE_CURVE_EXPONENT}"
        calibrated_test_probs = np.array([self._apply_calibration(prob) for prob in raw_test_probs], dtype=float)
        base_probability = _expected_value_to_probability(getattr(self.explainer, "expected_value", 0.5))
        _, calibrated_base_probability = self._calibration_details(base_probability)
        self.population_base_score = _map_probability_to_score(calibrated_base_probability)

        self.model_metrics = self._compute_metrics(y_test, raw_test_probs, calibrated_test_probs, dataset_meta)
        self.last_loaded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._save_artifacts()
        total_training_sample_size = int(len(X))
        return {
            "training_sample_size": total_training_sample_size,
            "synthetic_sample_count": synthetic_sample_count,
            "real_sample_count": real_sample_count if use_real_outcomes else 0,
            "real_label_ratio": round(
                (real_sample_count / total_training_sample_size) if use_real_outcomes and total_training_sample_size else 0.0,
                4,
            ),
            "real_outcomes_used": use_real_outcomes,
            "minimum_real_outcomes_required": REAL_OUTCOME_MIN_RECORDS,
            "feature_schema_version": TRAINING_SCHEMA_ID,
        }

    def _load_or_train(self) -> None:
        if not self._load_from_artifacts():
            self._train_model()

    def retrain(self, real_outcomes: list[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        training_summary = self._train_model(real_outcomes=real_outcomes)
        return {
            **self.health_summary(),
            "training_summary": training_summary,
        }

    def health_summary(self) -> Dict[str, Any]:
        return {
            "loaded": self.model is not None or self.backend == "heuristic",
            "backend": self.backend,
            "fallback_active": self.backend == "heuristic",
            "model_version": self.model_version,
            "model_artifact_path": self.model_artifact_path,
            "metadata_artifact_path": self.metadata_artifact_path,
            "calibration_artifact_path": self.calibration_artifact_path,
            "calibration_curve_artifact_path": self.calibration_curve_artifact_path,
            "calibration_method": self.calibration_method,
            "score_mapping": self.score_mapping,
            "metrics": self.model_metrics,
            "population_base_score": self.population_base_score,
            "last_loaded_at": self.last_loaded_at,
            "shap_available": self.explainer is not None,
        }

    def score(self, features: Dict[str, float]) -> Dict[str, Any]:
        feature_array = np.array([[features.get(name, 0.0) for name in FEATURE_NAMES]])

        if self.model is None or self.explainer is None:
            return self._fallback_score(features)

        if self.backend == "xgboost":
            dmatrix = xgb.DMatrix(feature_array, feature_names=FEATURE_NAMES)
            raw_prob = float(self.model.predict(dmatrix)[0])
            shap_values = self.explainer.shap_values(dmatrix)
        else:
            raw_prob = float(self.model.predict_proba(feature_array)[0][1])
            shap_values = self.explainer.shap_values(feature_array)

        isotonic_prob, calibrated_prob = self._calibration_details(raw_prob)
        credit_score = _map_probability_to_score(calibrated_prob)
        if self.population_base_score is not None:
            base_score = self.population_base_score
        else:
            base_probability = _expected_value_to_probability(getattr(self.explainer, "expected_value", 0.5))
            _, calibrated_base_probability = self._calibration_details(base_probability)
            base_score = _map_probability_to_score(calibrated_base_probability)

        shap_vals = shap_values[0][0] if isinstance(shap_values, list) else shap_values[0]
        feature_shap_pairs = list(zip(FEATURE_NAMES, shap_vals, feature_array[0]))
        feature_shap_pairs.sort(key=lambda x: abs(x[1]), reverse=True)
        top_reasons, all_shap, shap_waterfall = _build_waterfall_rows(
            base_score=base_score,
            final_score=credit_score,
            feature_shap_pairs=feature_shap_pairs,
            features=features,
            limit=5,
        )
        calibration_trace = _build_calibration_trace(
            raw_probability=raw_prob,
            isotonic_probability=isotonic_prob,
            calibrated_probability=calibrated_prob,
            default_probability=1.0 - calibrated_prob,
            method=self.calibration_method,
            curve_version=self.model_version,
            score_mapping=self.score_mapping,
            curve_points=self.model_metrics.get("calibration_curve", []),
        )

        monthly_revenue = features.get("upi_net_cash_flow", 0)
        if monthly_revenue <= 0:
            monthly_revenue = (
                features.get("eway_avg_bill_value", 200000)
                * features.get("eway_avg_monthly_bills", 10)
                * 0.3
            )

        return {
            "credit_score": credit_score,
            "probability": round(calibrated_prob, 4),
            "raw_probability": round(raw_prob, 4),
            "default_probability": round(1.0 - calibrated_prob, 4),
            "risk_band": get_risk_band(credit_score),
            "base_score": base_score,
            "top_reasons": top_reasons,
            "shap_reasons": top_reasons,
            "all_shap_values": all_shap,
            "shap_waterfall": shap_waterfall,
            "recommendation": recommend_loan(credit_score, abs(monthly_revenue)),
            "score_freshness": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "model_version": self.model_version,
            "model_metrics": self.model_metrics,
            "calibration": calibration_trace,
            "calibration_method": self.calibration_method,
            "score_mapping": self.score_mapping,
        }

    def _fallback_score(self, features: Dict[str, float]) -> Dict[str, Any]:
        pos = 0.0
        pos += min(features.get("gst_filing_rate", 0), 1.0) * 80
        pos += min(features.get("gst_on_time_pct", 0) / 100, 1.0) * 60
        pos += min(features.get("upi_regularity_score", 0) / 100, 1.0) * 50
        pos += min(features.get("upi_inflow_outflow_ratio", 0) / 2, 1.0) * 70
        pos += min(features.get("eway_avg_monthly_bills", 0) / 50, 1.0) * 40
        pos += features.get("overall_data_confidence", 0.5) * 50

        neg = 0.0
        neg += min(features.get("gst_avg_delay_days", 0) / 20, 1.0) * 60
        neg += min(features.get("gst_itc_variance_avg", 0) / 20, 1.0) * 50
        neg += min(features.get("upi_round_amount_pct", 0) / 30, 1.0) * 60
        neg += min(features.get("eway_cancellation_rate", 0) / 10, 1.0) * 40

        raw = float(np.clip((pos - neg + 300) / 650, 0.0, 1.0))
        credit_score = _map_probability_to_score(raw)
        base_score = 600

        feature_pairs: list[tuple[str, float, float]] = []
        for fname, fval, is_positive in [
            ("gst_filing_rate", features.get("gst_filing_rate", 0), True),
            ("gst_avg_delay_days", features.get("gst_avg_delay_days", 0), False),
            ("upi_regularity_score", features.get("upi_regularity_score", 0), True),
            ("upi_inflow_outflow_ratio", features.get("upi_inflow_outflow_ratio", 0), True),
            ("upi_round_amount_pct", features.get("upi_round_amount_pct", 0), False),
        ]:
            feature_pairs.append((fname, 0.1 if is_positive else -0.1, float(fval)))

        top_reasons, all_shap, shap_waterfall = _build_waterfall_rows(
            base_score=base_score,
            final_score=credit_score,
            feature_shap_pairs=feature_pairs,
            features=features,
            limit=5,
        )

        monthly_revenue = abs(features.get("upi_net_cash_flow", 500000))
        return {
            "credit_score": credit_score,
            "probability": round(raw, 4),
            "raw_probability": round(raw, 4),
            "default_probability": round(1.0 - raw, 4),
            "risk_band": get_risk_band(credit_score),
            "base_score": base_score,
            "top_reasons": top_reasons,
            "shap_reasons": top_reasons,
            "all_shap_values": all_shap,
            "shap_waterfall": shap_waterfall,
            "recommendation": recommend_loan(credit_score, monthly_revenue),
            "score_freshness": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "model_version": "fallback-heuristic-v1.0",
            "model_metrics": {},
            "calibration": _build_calibration_trace(
                raw_probability=raw,
                isotonic_probability=raw,
                calibrated_probability=raw,
                default_probability=1.0 - raw,
                method="identity",
                curve_version="fallback-heuristic-v1.0",
                score_mapping=f"non_linear_power_curve_{SCORE_CURVE_EXPONENT}",
                curve_points=[],
            ),
            "calibration_method": "identity",
            "score_mapping": f"non_linear_power_curve_{SCORE_CURVE_EXPONENT}",
        }


_scorer: MSMECreditScorer | None = None


def get_scorer() -> MSMECreditScorer:
    global _scorer
    if _scorer is None:
        _scorer = MSMECreditScorer()
    return _scorer


def reset_scorer() -> None:
    global _scorer
    _scorer = None
