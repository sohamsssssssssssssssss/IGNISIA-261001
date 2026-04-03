from __future__ import annotations

import copy
import logging
from typing import Any, Callable, Dict, List

import numpy as np


logger = logging.getLogger("intellicredit.simulator")


# Mapped to the closest equivalents in the current feature set.
CLEAN_BORROWER_TARGETS: Dict[str, float] = {
    "gst_avg_delay_days": 0.0,
    "gst_filing_rate": 1.0,
    "upi_round_amount_pct": 5.0,
    "upi_avg_daily_txns": 18.0,
    "upi_volume_growth": 12.0,
    "gst_itc_variance_avg": 0.0,
    "gst_on_time_pct": 95.0,
    "upi_regularity_score": 90.0,
}

ACTION_LABELS: Dict[str, str] = {
    "gst_avg_delay_days": "File GST returns on time",
    "gst_filing_rate": "Maintain consistent GST filing",
    "upi_round_amount_pct": "Reduce round-amount UPI transactions",
    "upi_avg_daily_txns": "Increase digital transaction volume",
    "upi_volume_growth": "Show consistent revenue growth",
    "gst_itc_variance_avg": "Clear GST reconciliation gaps",
    "gst_on_time_pct": "Maximize timely GST compliance",
    "upi_regularity_score": "Stabilize monthly cash flows",
}

MONTHLY_NUDGE_RATE = 0.18
TOP_N_FEATURES = 3
MIN_MONTHLY_SCORE_DELTA = 5


def get_top_negative_contributors(shap_values: Dict[str, float]) -> List[str]:
    sorted_features = sorted(shap_values.items(), key=lambda x: x[1])
    return [feat for feat, value in sorted_features if value < 0][:TOP_N_FEATURES]


def nudge_vector(
    feature_vector: Dict[str, Any],
    features_to_fix: List[str],
    month: int,
) -> Dict[str, Any]:
    nudged = copy.deepcopy(feature_vector)

    for feat in features_to_fix:
        if feat not in CLEAN_BORROWER_TARGETS:
            continue
        if feat not in nudged:
            continue

        current_val = float(nudged[feat])
        target_val = CLEAN_BORROWER_TARGETS[feat]
        gap = target_val - current_val
        fraction_closed = 1 - (1 - MONTHLY_NUDGE_RATE) ** month
        nudged[feat] = current_val + gap * fraction_closed

    return nudged


def compute_eligible_amount(score: int) -> int:
    if score >= 750:
        return 5_000_000
    if score >= 700:
        return 3_000_000
    if score >= 650:
        return 2_000_000
    if score >= 600:
        return 1_000_000
    if score >= 550:
        return 500_000
    return 0


def run_simulation(
    gstin: str,
    feature_vector: Dict[str, Any],
    shap_values: Dict[str, float],
    scorer_fn: Callable[[Dict[str, Any]], int],
    approval_threshold: int = 550,
    months: int = 6,
) -> Dict[str, Any]:
    base_score = int(np.clip(scorer_fn(feature_vector), 300, 900))
    top_features = get_top_negative_contributors(shap_values)

    trajectory = []
    crossed_threshold_month = None

    if not top_features:
        logger.info("Simulator found no negative SHAP drivers for %s", gstin)

    previous_score = base_score
    for month in range(1, months + 1):
        nudged_vector = nudge_vector(feature_vector, top_features, month)
        projected_score = int(np.clip(scorer_fn(nudged_vector), 300, 900))

        if top_features and projected_score <= previous_score:
            projected_score = min(900, previous_score + MIN_MONTHLY_SCORE_DELTA)
            logger.warning(
                "Simulator score floor applied for %s at month %s due to flat model response",
                gstin,
                month,
            )

        month_actions = []
        if month <= len(top_features):
            feat = top_features[month - 1]
            month_actions.append(ACTION_LABELS.get(feat, feat))

        crosses_threshold = projected_score >= approval_threshold and previous_score < approval_threshold
        if crosses_threshold and crossed_threshold_month is None:
            crossed_threshold_month = month

        trajectory.append(
            {
                "month": month,
                "score": projected_score,
                "actions": month_actions,
                "crosses_threshold": crosses_threshold,
            }
        )
        previous_score = projected_score

    final_score = trajectory[-1]["score"] if trajectory else base_score
    return {
        "gstin": gstin,
        "base_score": base_score,
        "approval_threshold": approval_threshold,
        "top_issues": [
            {
                "feature": feat,
                "label": ACTION_LABELS.get(feat, feat),
                "shap_impact": round(float(shap_values.get(feat, 0.0)), 4),
            }
            for feat in top_features
        ],
        "trajectory": trajectory,
        "crossed_threshold_month": crossed_threshold_month,
        "final_eligible_amount": compute_eligible_amount(final_score),
    }
