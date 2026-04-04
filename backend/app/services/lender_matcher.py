from __future__ import annotations

from typing import Any, Dict, List

from ..config.lender_config import LENDER_ARCHETYPES


class LenderMatcher:
    def __init__(self, lender_config: List[Dict[str, Any]] | None = None) -> None:
        self.lender_config = sorted(
            lender_config or LENDER_ARCHETYPES,
            key=lambda item: int(item.get("tier_rank", 0)),
            reverse=True,
        )

    def match_lenders(
        self,
        *,
        score: int,
        fraud_score: float,
        loan_amount: float,
        history_months: float,
    ) -> Dict[str, Any]:
        safe_loan_amount = float(max(0.0, loan_amount))
        evaluations = [
            self._evaluate_lender(
                lender,
                score=score,
                fraud_score=fraud_score,
                loan_amount=safe_loan_amount,
                history_months=history_months,
            )
            for lender in self.lender_config
        ]

        fully_qualified = [item for item in evaluations if item["status"] == "qualified"]
        borderline = [item for item in evaluations if item["status"] == "borderline"]
        not_yet_accessible = [item for item in evaluations if item["status"] == "not_qualified"]

        recommended = fully_qualified[0] if fully_qualified else None
        closest = (
            borderline[0]
            if borderline
            else min(
                evaluations,
                key=lambda item: (len(item["failed_conditions"]), -int(item["tier_rank"])),
            )
            if evaluations
            else None
        )

        if recommended is not None:
            summary = (
                f"{recommended['display_name']} is the best current fit because your score, fraud profile, "
                "business history, and requested loan amount all meet that tier's operating range."
            )
        elif closest is not None:
            closest_gap = closest["gap_statement"].rstrip(".")
            summary = (
                f"No lender tier is a full fit today. {closest['display_name']} is the closest option, "
                f"but {closest_gap[0].lower() + closest_gap[1:] if closest_gap else 'it still needs one more condition met'}."
            )
        else:
            summary = "No lender guidance could be generated."

        return {
            "requested_loan_amount": round(safe_loan_amount),
            "fraud_score": round(float(fraud_score), 1),
            "history_months": round(float(history_months), 1),
            "recommended_lender": self._compact_lender(recommended),
            "closest_lender": self._compact_lender(closest),
            "summary": summary,
            "qualified_lenders": [self._compact_lender(item) for item in fully_qualified],
            "borderline_lenders": [self._compact_lender(item) for item in borderline],
            "not_yet_accessible_lenders": [self._compact_lender(item) for item in not_yet_accessible],
            "all_lenders": [self._compact_lender(item) for item in evaluations],
        }

    def _evaluate_lender(
        self,
        lender: Dict[str, Any],
        *,
        score: int,
        fraud_score: float,
        loan_amount: float,
        history_months: float,
    ) -> Dict[str, Any]:
        checks = {
            "score": {
                "actual": int(score),
                "required_minimum": int(lender["minimum_score"]),
                "passed": score >= int(lender["minimum_score"]),
                "gap": max(0, int(lender["minimum_score"]) - int(score)),
            },
            "fraud_score": {
                "actual": round(float(fraud_score), 1),
                "required_maximum": float(lender["maximum_acceptable_fraud_score"]),
                "passed": float(fraud_score) <= float(lender["maximum_acceptable_fraud_score"]),
                "gap": max(0.0, float(fraud_score) - float(lender["maximum_acceptable_fraud_score"])),
            },
            "history_months": {
                "actual": round(float(history_months), 1),
                "required_minimum": float(lender["minimum_history_months"]),
                "passed": float(history_months) >= float(lender["minimum_history_months"]),
                "gap": max(0.0, float(lender["minimum_history_months"]) - float(history_months)),
            },
            "loan_amount": {
                "actual": round(float(loan_amount)),
                "required_minimum": float(lender["minimum_loan_amount"]),
                "required_maximum": float(lender["maximum_loan_amount"]),
                "passed": float(lender["minimum_loan_amount"]) <= float(loan_amount) <= float(lender["maximum_loan_amount"]),
                "gap_below": max(0.0, float(lender["minimum_loan_amount"]) - float(loan_amount)),
                "gap_above": max(0.0, float(loan_amount) - float(lender["maximum_loan_amount"])),
            },
        }

        failed_conditions = [
            name
            for name, payload in checks.items()
            if not payload["passed"]
        ]
        status = "qualified" if not failed_conditions else ("borderline" if len(failed_conditions) == 1 else "not_qualified")

        return {
            **lender,
            "status": status,
            "qualification_status": status,
            "checks": checks,
            "failed_conditions": failed_conditions,
            "gap_statement": self._build_gap_statement(lender, checks, failed_conditions),
            "plain_english_reason": self._build_reason(lender, status, checks, failed_conditions),
        }

    def _build_gap_statement(
        self,
        lender: Dict[str, Any],
        checks: Dict[str, Dict[str, Any]],
        failed_conditions: List[str],
    ) -> str:
        if not failed_conditions:
            return f"You currently meet all qualifying conditions for {lender['display_name']}."

        statements: List[str] = []
        for condition in failed_conditions:
            if condition == "score":
                statements.append(
                    f"you need {int(checks['score']['gap'])} more score points to qualify for {lender['display_name']}"
                )
            elif condition == "fraud_score":
                statements.append(
                    f"your fraud risk needs to fall by {int(round(checks['fraud_score']['gap']))} points for {lender['display_name']}"
                )
            elif condition == "history_months":
                statements.append(
                    f"your business needs {int(round(checks['history_months']['gap']))} more months of history for {lender['display_name']}"
                )
            elif condition == "loan_amount":
                if checks["loan_amount"]["gap_below"] > 0:
                    statements.append(
                        f"your requested loan amount is INR {int(round(checks['loan_amount']['gap_below'])):,} below the practical minimum ticket size for {lender['display_name']}"
                    )
                else:
                    statements.append(
                        f"your requested loan amount is INR {int(round(checks['loan_amount']['gap_above'])):,} above the practical maximum range for {lender['display_name']}"
                    )
        if len(statements) == 1:
            return f"{statements[0][0].upper() + statements[0][1:]}."
        joined = "; ".join(statements)
        return f"{joined[0].upper() + joined[1:]}."

    def _build_reason(
        self,
        lender: Dict[str, Any],
        status: str,
        checks: Dict[str, Dict[str, Any]],
        failed_conditions: List[str],
    ) -> str:
        if status == "qualified":
            return (
                f"{lender['display_name']} fits because your score is {checks['score']['actual']}, "
                f"fraud score is {checks['fraud_score']['actual']}, business history is {checks['history_months']['actual']} months, "
                f"and the requested amount sits inside its normal operating band."
            )
        if status == "borderline":
            return (
                f"You are close to {lender['display_name']}: "
                f"{self._build_gap_statement(lender, checks, failed_conditions)}"
            )
        return (
            f"{lender['display_name']} is not accessible yet because "
            f"{self._build_gap_statement(lender, checks, failed_conditions).rstrip('.').lower()}."
        )

    def _compact_lender(self, lender: Dict[str, Any] | None) -> Dict[str, Any] | None:
        if lender is None:
            return None
        return {
            "key": lender["key"],
            "display_name": lender["display_name"],
            "tier_rank": lender["tier_rank"],
            "status": lender["status"],
            "qualification_status": lender["qualification_status"],
            "gap_statement": lender["gap_statement"],
            "plain_english_reason": lender["plain_english_reason"],
            "typical_interest_rate_range": lender["typical_interest_rate_range"],
            "typical_processing_time_days": lender["typical_processing_time_days"],
            "notes": lender["notes"],
            "checks": lender["checks"],
            "failed_conditions": lender["failed_conditions"],
        }
