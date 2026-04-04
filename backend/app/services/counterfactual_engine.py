from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable, Dict, List, Literal


ConfidenceLabel = Literal["high", "medium"]


@dataclass(frozen=True)
class CounterfactualFeatureSpec:
    feature_key: str
    feature_name: str
    direction: Literal["up", "down"]
    step_size: float
    minimum_target_delta: int
    timeframe_days: str
    timeframe_rank_days: int
    action_template: str
    target_limit_fn: Callable[[float, Dict[str, float]], float]


ACTIONABLE_FEATURE_SPECS: List[CounterfactualFeatureSpec] = [
    CounterfactualFeatureSpec(
        feature_key="gst_filing_rate",
        feature_name="GST filing rate",
        direction="up",
        step_size=0.05,
        minimum_target_delta=20,
        timeframe_days="30-45",
        timeframe_rank_days=45,
        action_template=(
            "File every GST return on or before the due date until your filing rate reaches {target_display}."
        ),
        target_limit_fn=lambda current, _features: 1.0,
    ),
    CounterfactualFeatureSpec(
        feature_key="upi_avg_daily_txns",
        feature_name="UPI transaction frequency",
        direction="up",
        step_size=1.0,
        minimum_target_delta=20,
        timeframe_days="21-45",
        timeframe_rank_days=45,
        action_template=(
            "Shift more collections and supplier payments through UPI to raise transaction frequency to {target_display}."
        ),
        target_limit_fn=lambda current, _features: max(current * 2.0, current + 6.0),
    ),
    CounterfactualFeatureSpec(
        feature_key="upi_regularity_score",
        feature_name="UPI cash-flow regularity",
        direction="up",
        step_size=5.0,
        minimum_target_delta=20,
        timeframe_days="60-90",
        timeframe_rank_days=90,
        action_template=(
            "Maintain steadier daily inflows and avoid lumpy payment gaps until your regularity score reaches {target_display}."
        ),
        target_limit_fn=lambda current, _features: 100.0,
    ),
    CounterfactualFeatureSpec(
        feature_key="eway_cancellation_rate",
        feature_name="E-way bill cancellation rate",
        direction="down",
        step_size=2.0,
        minimum_target_delta=20,
        timeframe_days="14-21",
        timeframe_rank_days=21,
        action_template=(
            "Tighten dispatch controls and pre-dispatch validation so your cancellation rate falls to {target_display}."
        ),
        target_limit_fn=lambda current, _features: 0.5,
    ),
    CounterfactualFeatureSpec(
        feature_key="gst_e_invoice_velocity",
        feature_name="GST reported sales momentum",
        direction="up",
        step_size=5.0,
        minimum_target_delta=20,
        timeframe_days="30-60",
        timeframe_rank_days=60,
        action_template=(
            "Increase genuine billed activity and keep GST-reported sales momentum rising until you sustain {target_display}."
        ),
        target_limit_fn=lambda current, _features: min(max(current * 2.0, current + 20.0), 240.0),
    ),
    CounterfactualFeatureSpec(
        feature_key="upi_net_cash_flow",
        feature_name="UPI net cash flow",
        direction="up",
        step_size=50_000.0,
        minimum_target_delta=20,
        timeframe_days="30-60",
        timeframe_rank_days=60,
        action_template=(
            "Improve net operating inflows, speed up collections, and tighten payment timing until net cash flow reaches {target_display}."
        ),
        target_limit_fn=lambda current, _features: max(current + max(abs(current), 200_000.0), 250_000.0),
    ),
]


class CounterfactualEngine:
    def generate_recommendations(
        self,
        gstin: str,
        feature_vector: Dict[str, float],
        current_score: int,
        model: Any,
        *,
        top_n: int = 5,
    ) -> Dict[str, Any]:
        analyses = []
        for spec in ACTIONABLE_FEATURE_SPECS:
            analysis = self._analyze_feature(spec, feature_vector, current_score, model)
            if analysis is not None:
                analyses.append(analysis)

        analyses.sort(
            key=lambda item: (
                -item["max_achievable_improvement"],
                item["timeframe_rank_days"],
                item["feature_name"],
            )
        )
        selected = analyses[:top_n]
        combined_projection = self._build_combined_projection(
            feature_vector,
            selected,
            current_score,
            model,
        )

        return {
            "gstin": gstin,
            "base_score": current_score,
            "combined_projected_score": combined_projection["combined_projected_score"],
            "combined_score_improvement": combined_projection["combined_score_improvement"],
            "naive_sum_score_improvement": combined_projection["naive_sum_score_improvement"],
            "recommendations": [
                {
                    "feature_key": item["feature_key"],
                    "feature_name": item["feature_name"],
                    "current_value": item["current_value"],
                    "current_value_display": item["current_value_display"],
                    "target_value": item["target_value"],
                    "target_value_display": item["target_value_display"],
                    "estimated_score_improvement": item["estimated_score_improvement"],
                    "confidence": item["confidence"],
                    "action": item["action"],
                    "timeframe_days": item["timeframe_days"],
                }
                for item in selected
            ],
        }

    def apply_feature_change(
        self,
        feature_vector: Dict[str, float],
        feature_key: str,
        target_value: float,
    ) -> Dict[str, float]:
        return self._apply_feature_change(feature_vector, feature_key, target_value)

    def score_features(self, feature_vector: Dict[str, float], model: Any) -> int:
        return self._score_features(feature_vector, model)

    def _analyze_feature(
        self,
        spec: CounterfactualFeatureSpec,
        feature_vector: Dict[str, float],
        current_score: int,
        model: Any,
    ) -> Dict[str, Any] | None:
        current_value = float(feature_vector.get(spec.feature_key, 0.0))
        candidate_values = self._build_nudge_values(spec, current_value, feature_vector)
        if not candidate_values:
            return None

        score_curve = []
        for candidate in candidate_values:
            nudged_vector = self._apply_feature_change(feature_vector, spec.feature_key, candidate)
            projected_score = self._score_features(nudged_vector, model)
            score_curve.append(
                {
                    "target_value": candidate,
                    "projected_score": projected_score,
                    "delta": projected_score - current_score,
                }
            )

        if not score_curve:
            return None

        viable_curve = [point for point in score_curve if point["delta"] > 0]
        if not viable_curve:
            return None

        best_point = max(viable_curve, key=lambda item: (item["delta"], -item["target_value"]))
        recommended_point = next(
            (point for point in viable_curve if point["delta"] >= spec.minimum_target_delta),
            best_point,
        )
        confidence = self._derive_confidence(score_curve, spec.direction)
        target_value = float(recommended_point["target_value"])

        return {
            "feature_key": spec.feature_key,
            "feature_name": spec.feature_name,
            "current_value": current_value,
            "current_value_display": self._format_value(spec.feature_key, current_value),
            "target_value": target_value,
            "target_value_display": self._format_value(spec.feature_key, target_value),
            "estimated_score_improvement": int(recommended_point["delta"]),
            "max_achievable_improvement": int(best_point["delta"]),
            "confidence": confidence,
            "action": spec.action_template.format(
                current_display=self._format_value(spec.feature_key, current_value),
                target_display=self._format_value(spec.feature_key, target_value),
            ),
            "timeframe_days": spec.timeframe_days,
            "timeframe_rank_days": spec.timeframe_rank_days,
            "score_curve": score_curve,
        }

    def _build_nudge_values(
        self,
        spec: CounterfactualFeatureSpec,
        current_value: float,
        feature_vector: Dict[str, float],
    ) -> List[float]:
        target_limit = float(spec.target_limit_fn(current_value, feature_vector))
        values: List[float] = []

        if spec.direction == "up":
            candidate = current_value + spec.step_size
            while candidate <= target_limit + 1e-9:
                values.append(candidate)
                candidate += spec.step_size
        else:
            candidate = current_value - spec.step_size
            while candidate >= target_limit - 1e-9:
                values.append(max(candidate, target_limit))
                candidate -= spec.step_size

        deduped = []
        seen = set()
        for value in values:
            rounded = round(value, 6)
            if rounded in seen:
                continue
            if math.isclose(rounded, current_value, abs_tol=1e-9):
                continue
            seen.add(rounded)
            deduped.append(rounded)
        return deduped

    def _apply_feature_change(
        self,
        feature_vector: Dict[str, float],
        feature_key: str,
        target_value: float,
    ) -> Dict[str, float]:
        nudged = dict(feature_vector)
        nudged[feature_key] = float(target_value)

        # Keep deterministic derived interactions aligned with the nudged base signal.
        if feature_key == "gst_filing_rate":
            nudged["gst_filing_history_interaction"] = round(
                nudged["gst_filing_rate"] * nudged.get("history_months_active", 0.0),
                4,
            )
        if feature_key == "upi_regularity_score":
            nudged["upi_regularity_history_interaction"] = round(
                nudged["upi_regularity_score"] * nudged.get("history_months_active", 0.0),
                4,
            )
        return nudged

    def _score_features(self, feature_vector: Dict[str, float], model: Any) -> int:
        if hasattr(model, "predict_credit_score"):
            return int(model.predict_credit_score(feature_vector))
        if hasattr(model, "score"):
            return int(model.score(feature_vector)["credit_score"])
        raise TypeError("Model does not expose a compatible scoring interface")

    def _derive_confidence(
        self,
        score_curve: List[Dict[str, float]],
        direction: Literal["up", "down"],
    ) -> ConfidenceLabel:
        monotone_pairs = 0
        total_pairs = max(len(score_curve) - 1, 1)
        for previous, current in zip(score_curve, score_curve[1:]):
            if current["delta"] >= previous["delta"] - 1:
                monotone_pairs += 1
        monotone_ratio = monotone_pairs / total_pairs
        max_delta = max(point["delta"] for point in score_curve)
        if monotone_ratio >= 0.8 and max_delta >= 12:
            return "high"
        return "medium"

    def _build_combined_projection(
        self,
        feature_vector: Dict[str, float],
        recommendations: List[Dict[str, Any]],
        current_score: int,
        model: Any,
    ) -> Dict[str, int]:
        combined_vector = dict(feature_vector)
        naive_sum = 0
        for item in recommendations:
            combined_vector = self._apply_feature_change(
                combined_vector,
                item["feature_key"],
                float(item["target_value"]),
            )
            naive_sum += int(item["estimated_score_improvement"])

        combined_score = self._score_features(combined_vector, model)
        return {
            "combined_projected_score": combined_score,
            "combined_score_improvement": int(combined_score - current_score),
            "naive_sum_score_improvement": naive_sum,
        }

    def _format_value(self, feature_key: str, value: float) -> str:
        if feature_key == "gst_filing_rate":
            return f"{round(value * 100):.0f}%"
        if feature_key == "upi_avg_daily_txns":
            return f"{round(value):.0f}/day"
        if feature_key == "upi_regularity_score":
            return f"{round(value):.0f}/100"
        if feature_key == "eway_cancellation_rate":
            return f"{value:.1f}%"
        if feature_key == "gst_e_invoice_velocity":
            return f"{round(value):.0f} invoices/month"
        if feature_key == "upi_net_cash_flow":
            sign = "-" if value < 0 else ""
            return f"{sign}INR {abs(round(value)):,.0f}/month"
        return f"{value:.2f}"
