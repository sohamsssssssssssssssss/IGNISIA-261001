"""
Prompt-context builder for underwriting narrative and chat generation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List


SYSTEM_PROMPT = (
    "You are a senior underwriting analyst. Use only the provided context, "
    "quote exact numbers when available, and avoid giving a final sanction "
    "decision unless explicitly requested."
)


class ContextBuilder:
    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_scoring_context(
        self,
        gstin: str,
        score_payload: Dict[str, Any],
        similar_cases: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
    ) -> str:
        lines = [
            "[BUSINESS PROFILE]",
            f"GSTIN: {gstin}",
            f"Company: {score_payload.get('company_name')}",
            f"Credit Score: {score_payload.get('credit_score')}",
            f"Risk Band: {score_payload.get('risk_band', {}).get('band') if isinstance(score_payload.get('risk_band'), dict) else score_payload.get('risk_band')}",
            f"Fraud Risk: {score_payload.get('fraud_detection', {}).get('circular_risk')}",
            "",
            "[TOP REASONS]",
        ]
        for reason in score_payload.get("top_reasons", []):
            lines.append(f"- {reason.get('feature') or reason.get('feature_key')}: {reason.get('reason')}")
        lines.extend(["", "[SIMILAR CASES]"])
        for case in similar_cases:
            lines.append(
                f"- {case.get('gstin')}: score {case.get('credit_score')} | "
                f"similarity {case.get('similarity')} | outcome {case.get('outcome', {}).get('status')}"
            )
        lines.extend(["", "[RULES]"])
        for rule in rules:
            lines.append(f"- {rule.get('text')}")
        return "\n".join(lines)

    def build_chat_context(
        self,
        gstin: str,
        score_payload: Dict[str, Any],
        similar_cases: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
        conversation_history: List[Dict[str, str]],
        new_message: str,
    ) -> str:
        history_lines = [f"{item['role']}: {item['content']}" for item in conversation_history]
        return "\n".join(
            [
                self.build_scoring_context(gstin, score_payload, similar_cases, rules),
                "",
                "[CONVERSATION HISTORY]",
                *history_lines,
                "",
                "[NEW USER MESSAGE]",
                new_message,
            ]
        )


@lru_cache(maxsize=1)
def get_context_builder() -> ContextBuilder:
    return ContextBuilder()
