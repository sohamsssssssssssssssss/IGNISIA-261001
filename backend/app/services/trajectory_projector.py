from __future__ import annotations

from typing import Any, Dict, List

from ..config.lender_config import LENDER_ARCHETYPES
from .counterfactual_engine import CounterfactualEngine
from .lender_matcher import LenderMatcher


COMPLIANCE_CURVES: Dict[str, Dict[int, float]] = {
    "gst_filing_rate": {30: 0.50, 60: 0.85, 90: 1.0},
    "upi_avg_daily_txns": {30: 0.60, 60: 0.90, 90: 1.0},
    "upi_regularity_score": {30: 0.40, 60: 0.75, 90: 1.0},
    "eway_cancellation_rate": {30: 0.70, 60: 0.90, 90: 1.0},
    "gst_e_invoice_velocity": {30: 0.50, 60: 0.85, 90: 1.0},
    "upi_net_cash_flow": {30: 0.50, 60: 0.80, 90: 1.0},
}
TRAJECTORY_DAYS = [0, 30, 60, 90]
PASSIVE_DRIFT_POINTS_PER_30_DAYS = 2.0


class TrajectoryProjector:
    def __init__(
        self,
        *,
        counterfactual_engine: CounterfactualEngine | None = None,
        lender_matcher: LenderMatcher | None = None,
        lender_thresholds: List[Dict[str, Any]] | None = None,
    ) -> None:
        self.counterfactual_engine = counterfactual_engine or CounterfactualEngine()
        self.lender_thresholds = lender_thresholds or LENDER_ARCHETYPES
        self.lender_matcher = lender_matcher or LenderMatcher(self.lender_thresholds)

    def project(
        self,
        *,
        feature_vector: Dict[str, float],
        current_score: int,
        counterfactual_result: Dict[str, Any],
        model: Any,
        fraud_score: float,
        loan_amount: float,
        history_months: float,
    ) -> Dict[str, Any]:
        action_curve = [
            {
                "day": day,
                "score": self._score_at_day(
                    day=day,
                    feature_vector=feature_vector,
                    recommendations=counterfactual_result.get("recommendations", []),
                    current_score=current_score,
                    model=model,
                ),
            }
            for day in TRAJECTORY_DAYS
        ]
        passive_curve = [
            {
                "day": day,
                "score": int(round(current_score + PASSIVE_DRIFT_POINTS_PER_30_DAYS * (day / 30.0))),
            }
            for day in TRAJECTORY_DAYS
        ]
        unlock_events = self._build_lender_unlock_events(
            action_curve=action_curve,
            fraud_score=fraud_score,
            loan_amount=loan_amount,
            history_months=history_months,
        )

        return {
            "current_score": current_score,
            "with_action": action_curve,
            "no_action": passive_curve,
            "target_score_day_90": action_curve[-1]["score"],
            "lender_unlock_events": unlock_events,
        }

    def _score_at_day(
        self,
        *,
        day: int,
        feature_vector: Dict[str, float],
        recommendations: List[Dict[str, Any]],
        current_score: int,
        model: Any,
    ) -> int:
        if day == 0 or not recommendations:
            return int(current_score)

        projected_vector = dict(feature_vector)
        for recommendation in recommendations:
            current_value = float(recommendation["current_value"])
            target_value = float(recommendation["target_value"])
            completion_ratio = self._completion_ratio(recommendation["feature_key"], day)
            partial_target = current_value + ((target_value - current_value) * completion_ratio)
            projected_vector = self.counterfactual_engine.apply_feature_change(
                projected_vector,
                recommendation["feature_key"],
                partial_target,
            )
        return self.counterfactual_engine.score_features(projected_vector, model)

    def _completion_ratio(self, feature_key: str, day: int) -> float:
        if day <= 0:
            return 0.0
        curve = COMPLIANCE_CURVES.get(feature_key, {30: 0.5, 60: 0.8, 90: 1.0})
        if day in curve:
            return float(curve[day])
        earlier_days = [point for point in curve if point < day]
        later_days = [point for point in curve if point > day]
        if not earlier_days:
            first_day = min(curve)
            return float(curve[first_day]) * (day / first_day)
        if not later_days:
            return float(curve[max(curve)])
        left_day = max(earlier_days)
        right_day = min(later_days)
        left_value = float(curve[left_day])
        right_value = float(curve[right_day])
        ratio = (day - left_day) / (right_day - left_day)
        return left_value + ((right_value - left_value) * ratio)

    def _build_lender_unlock_events(
        self,
        *,
        action_curve: List[Dict[str, int]],
        fraud_score: float,
        loan_amount: float,
        history_months: float,
    ) -> List[Dict[str, Any]]:
        unlock_events: List[Dict[str, Any]] = []
        previously_qualified: set[str] = set()

        for day in range(0, 91):
            interpolated_score = self._interpolate_score(action_curve, day)
            projected_history = float(history_months) + (day / 30.0)
            lender_result = self.lender_matcher.match_lenders(
                score=interpolated_score,
                fraud_score=fraud_score,
                loan_amount=loan_amount,
                history_months=projected_history,
            )
            currently_qualified = {
                lender["key"]
                for lender in lender_result.get("qualified_lenders", [])
            }

            newly_qualified = currently_qualified - previously_qualified
            for lender in lender_result.get("qualified_lenders", []):
                if lender["key"] not in newly_qualified:
                    continue
                unlock_events.append(
                    {
                        "day": day,
                        "lender_key": lender["key"],
                        "lender_type": lender["display_name"],
                        "message": f"At this trajectory, you unlock {lender['display_name']} eligibility around day {day}.",
                    }
                )
            previously_qualified = currently_qualified

        return unlock_events

    def _interpolate_score(self, action_curve: List[Dict[str, int]], day: int) -> int:
        if day <= action_curve[0]["day"]:
            return int(action_curve[0]["score"])
        if day >= action_curve[-1]["day"]:
            return int(action_curve[-1]["score"])

        for left, right in zip(action_curve, action_curve[1:]):
            if left["day"] <= day <= right["day"]:
                if left["day"] == right["day"]:
                    return int(left["score"])
                fraction = (day - left["day"]) / (right["day"] - left["day"])
                interpolated = left["score"] + ((right["score"] - left["score"]) * fraction)
                return int(round(interpolated))
        return int(action_curve[-1]["score"])
