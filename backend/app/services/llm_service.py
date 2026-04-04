"""
LLM orchestration for underwriting narratives and stateful chat.
Prefers the unified local-first client and only uses Anthropic as a final
fallback when the unified client could not do better than the template path.
"""

from __future__ import annotations

import os
import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Sequence

from ..core.session_store import get_session_store
from ..services.context_builder import get_context_builder
from ..services.llm_client import llm

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - optional dependency in some envs
    Anthropic = None


ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
NARRATIVE_TEMPERATURE = 0.3
CHAT_TEMPERATURE = 0.3
OWNER_NARRATIVE_TEMPERATURE = 0.4
OWNER_NARRATIVE_SYSTEM_PROMPT = (
    "Write in a warm, direct tone as if advising a close friend who owns a small business. "
    "Write exactly 3 to 4 sentences. Do not use financial or statistical jargon. "
    "Do not mention SHAP, XGBoost, feature vectors, model calibration, deltas, or probabilities. "
    "End with one specific actionable next step the business owner can take this week."
)
OWNER_NARRATIVE_BANNED_TERMS = (
    "shap",
    "xgboost",
    "feature vector",
    "calibration",
    "probability",
    "delta",
    "counterfactual",
    "logit",
    "gradient boosting",
)
OWNER_REASON_TRANSLATIONS = {
    "gst_filing_rate": {
        "positive": "your GST returns have been filed consistently",
        "negative": "missed or late GST returns are pulling the score down",
    },
    "gst_filing_history_interaction": {
        "positive": "steady GST filing over time is building lender confidence",
        "negative": "the business is still too early in its GST track record for lenders to feel fully comfortable",
    },
    "maturity_penalty_umbrella": {
        "negative": "the business is still young, so lenders want to see more months of stable activity",
    },
    "history_months_active": {
        "positive": "the business now has enough operating history to look more stable",
        "negative": "the business is still young, so lenders want to see more operating history",
    },
    "upi_avg_daily_txns": {
        "positive": "your day-to-day digital payment activity looks healthy",
        "negative": "day-to-day UPI activity is still thin for the level of credit you want",
    },
    "upi_regularity_score": {
        "positive": "cash coming in and going out looks steady week after week",
        "negative": "cash flow still looks uneven from week to week",
    },
    "upi_regularity_history_interaction": {
        "positive": "steady UPI patterns over time are helping your case",
        "negative": "your payment pattern has not been stable for long enough yet",
    },
    "eway_cancellation_rate": {
        "positive": "shipment execution looks disciplined with few cancellations",
        "negative": "too many e-way bills are being cancelled after issue",
    },
    "gst_e_invoice_velocity": {
        "positive": "reported billed activity shows active business movement",
        "negative": "reported billed sales activity still looks softer than lenders prefer",
    },
    "upi_net_cash_flow": {
        "positive": "more money is coming in than going out through UPI",
        "negative": "money going out through UPI is still too close to or above inflows",
    },
    "overall_data_confidence": {
        "positive": "there is enough business data on record for lenders to trust the picture",
        "negative": "there is still limited business data on record",
    },
}
OWNER_RECOMMENDATION_PHRASES = {
    "gst_filing_rate": "bring GST filing discipline up by filing each return on time",
    "upi_avg_daily_txns": "increase how many customer and supplier payments move through UPI each day",
    "upi_regularity_score": "make day-to-day cash flow more even and predictable",
    "eway_cancellation_rate": "reduce e-way bill cancellations through tighter dispatch checks",
    "gst_e_invoice_velocity": "show stronger genuine billed sales through GST invoices",
    "upi_net_cash_flow": "keep more money coming in than going out through UPI",
}


class LLMService:
    def __init__(
        self,
        *,
        retrieval_service=None,
        context_builder=None,
        session_store=None,
        anthropic_client=None,
        fallback_llm=None,
    ) -> None:
        if retrieval_service is None:
            from ..services.retrieval_service import get_retrieval_service

            retrieval_service = get_retrieval_service()
        self.retrieval_service = retrieval_service
        self.context_builder = context_builder or get_context_builder()
        self.session_store = session_store or get_session_store()
        self.fallback_llm = fallback_llm or llm
        self.anthropic_client = anthropic_client or self._build_anthropic_client()

    def generate_narrative(self, gstin: str, score_payload: Dict[str, Any]) -> Dict[str, Any]:
        similar_cases = self.retrieval_service.get_similar_cases(gstin, score_payload, k=3)
        rules = self.retrieval_service.get_relevant_rules(score_payload, k=5)
        context = self.context_builder.build_scoring_context(gstin, score_payload, similar_cases, rules)
        prompt = (
            "Write a 3-paragraph underwriting brief.\n"
            "Paragraph 1: What this business looks like and why it scored this way.\n"
            "Paragraph 2: Key risk factors a loan officer should know.\n"
            "Paragraph 3: Recommendation and what would improve the score.\n"
            "Use only the provided context and cite specific numbers from the score payload.\n\n"
            f"{context}"
        )
        response_text, model_used = self._generate_text(
            prompt=prompt,
            max_tokens=1000,
            temperature=NARRATIVE_TEMPERATURE,
        )
        narrative_sections = self._structure_narrative(response_text)
        sources = self._build_sources(similar_cases, rules)
        return {
            "narrative": response_text,
            "narrative_sections": narrative_sections,
            "narrative_text": response_text,
            "sources": sources,
            "model_used": model_used,
        }

    def generate_owner_narrative(self, score_payload: Dict[str, Any]) -> Dict[str, str]:
        prompt = self._build_owner_narrative_prompt(score_payload)
        narrative_text, model_used = self._generate_text(
            prompt=prompt,
            max_tokens=220,
            temperature=OWNER_NARRATIVE_TEMPERATURE,
            system_prompt=OWNER_NARRATIVE_SYSTEM_PROMPT,
        )

        safe_text = self._ensure_owner_safe_output(narrative_text)
        if model_used == "template-fallback" or safe_text is None:
            safe_text = self._build_owner_narrative_fallback(score_payload)
            model_used = "owner-template-fallback"

        return {
            "text": safe_text,
            "model_used": model_used,
        }

    def chat(
        self,
        gstin: str,
        score_payload: Dict[str, Any],
        message: str,
        session_id: str | None = None,
    ) -> Dict[str, Any]:
        active_session_id = self.session_store.get_or_create_session(gstin, session_id)
        history = self.session_store.get_history(active_session_id)
        similar_cases = self.retrieval_service.get_similar_cases(gstin, score_payload, k=3)
        rules = self.retrieval_service.get_relevant_rules(score_payload, k=5)
        question_context = self.retrieval_service.get_context_for_question(message, gstin, k=5)
        base_context = self.context_builder.build_chat_context(
            gstin,
            score_payload,
            similar_cases,
            rules,
            history,
            message,
        )
        prompt = "\n\n".join(
            [
                base_context,
                "[QUESTION-SPECIFIC RETRIEVAL]",
                *[
                    (
                        f"{item['collection']} | similarity={item['similarity']:.3f} | "
                        f"text={item['text']}"
                    )
                    for item in question_context
                ],
                "Answer the new user message directly. Reference the business-specific numbers in the context.",
            ]
        )
        reply, model_used = self._generate_text(
            prompt=prompt,
            max_tokens=800,
            temperature=CHAT_TEMPERATURE,
        )

        sources = self._build_sources(similar_cases, rules, question_context)
        self.session_store.append_message(active_session_id, "user", message, [])
        self.session_store.append_message(active_session_id, "assistant", reply, sources)
        return {
            "reply": reply,
            "sources": sources,
            "session_id": active_session_id,
            "sessionId": active_session_id,
            "model_used": model_used,
        }

    def _generate_text(
        self,
        *,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: str | None = None,
    ) -> tuple[str, str]:
        resolved_system_prompt = system_prompt or self.context_builder.get_system_prompt()
        fallback_prompt = (
            f"{resolved_system_prompt}\n\n"
            f"{prompt}\n\n"
            "If fraud is detected, flag it prominently. Do not make the final approval decision."
        )
        if hasattr(self.fallback_llm, "generate_sync_with_source"):
            text, source = self.fallback_llm.generate_sync_with_source(
                fallback_prompt,
                max_tokens=max_tokens,
            )
        else:
            text = self.fallback_llm.generate_sync(fallback_prompt, max_tokens=max_tokens)
            source = "fallback-llm"

        if source != "template-fallback":
            return text, source

        if self.anthropic_client is not None:
            try:
                message = self.anthropic_client.messages.create(
                    model=ANTHROPIC_MODEL,
                    system=resolved_system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                blocks = []
                for block in getattr(message, "content", []):
                    value = getattr(block, "text", None)
                    if value:
                        blocks.append(value)
                candidate = "\n".join(blocks).strip()
                if candidate:
                    return candidate, ANTHROPIC_MODEL
            except Exception:
                pass

        return text, source

    def _build_owner_narrative_prompt(self, score_payload: Dict[str, Any]) -> str:
        score = int(score_payload.get("credit_score", 0))
        risk_band = self._normalize_risk_band_label(score_payload.get("risk_band", {}).get("band"))
        top_reasons = [
            self._translate_reason_for_owner(reason)
            for reason in score_payload.get("top_reasons", [])[:3]
        ]
        top_reasons = [reason for reason in top_reasons if reason]

        counterfactual = score_payload.get("counterfactual_recommendations") or {}
        recommendations = counterfactual.get("recommendations") or []
        top_recommendation = recommendations[0] if recommendations else None
        trajectory = score_payload.get("score_trajectory") or {}
        lender_recommendations = score_payload.get("lender_recommendations") or {}
        recommended_lender = lender_recommendations.get("recommended_lender")
        closest_lender = lender_recommendations.get("closest_lender")

        lender_summary = (
            f"Best lender fit today: {recommended_lender['display_name']} because {recommended_lender['plain_english_reason']}"
            if recommended_lender
            else f"Closest lender tier: {closest_lender['display_name']} but {closest_lender['gap_statement']}"
            if closest_lender
            else "No lender tier is fully accessible today."
        )

        lines = [
            f"Score: {score}/900",
            f"Risk band: {risk_band}",
        ]
        if top_reasons:
            lines.append("Main reasons:")
            lines.extend([f"- {reason}" for reason in top_reasons[:3]])
        if top_recommendation:
            lines.append(
                "Most impactful change: "
                f"{self._translate_recommendation_for_owner(top_recommendation)}. "
                f"Current state {top_recommendation['current_value_display']}, target {top_recommendation['target_value_display']}, "
                f"estimated lift {top_recommendation['estimated_score_improvement']} points."
            )
        if trajectory:
            lines.append(
                f"Projected score at day 90 if they follow the plan: {trajectory.get('target_score_day_90', score)}."
            )
        lines.append(lender_summary)
        lines.append(self._owner_fraud_sentence(score_payload))
        lines.append("Write exactly 3 to 4 sentences.")
        return "\n".join(lines)

    def _translate_reason_for_owner(self, reason: Dict[str, Any]) -> str:
        feature_key = str(reason.get("feature_key") or "")
        direction = "positive" if float(reason.get("shap_value", 0.0)) >= 0 else "negative"
        translation = OWNER_REASON_TRANSLATIONS.get(feature_key, {}).get(direction)
        if translation:
            return translation

        raw_text = str(reason.get("reason") or "").strip()
        if not raw_text:
            return ""
        sanitized = re.sub(r"\([+-]?\d+\s*pts?\)", "", raw_text, flags=re.IGNORECASE).strip()
        for term in OWNER_NARRATIVE_BANNED_TERMS:
            if term in sanitized.lower():
                return ""
        return sanitized

    def _translate_recommendation_for_owner(self, recommendation: Dict[str, Any]) -> str:
        feature_key = str(recommendation.get("feature_key") or "")
        phrase = OWNER_RECOMMENDATION_PHRASES.get(feature_key)
        if phrase:
            return phrase
        return str(recommendation.get("action") or "focus on the highest-impact improvement")

    def _normalize_risk_band_label(self, value: Any) -> str:
        label = str(value or "").strip()
        if not label:
            return "unknown range"
        return label.replace("_", " ").lower()

    def _owner_fraud_sentence(self, score_payload: Dict[str, Any]) -> str:
        fraud = score_payload.get("fraud_detection") or {}
        if fraud.get("circular_risk") in {"HIGH", "MEDIUM"}:
            return (
                "Fraud warning: unusual payment loops were detected, so lenders will want that cleaned up before approving credit."
            )
        return "Fraud check: no major circular payment warning is currently holding the case back."

    def _ensure_owner_safe_output(self, text: str) -> str | None:
        compact = re.sub(r"\s+", " ", (text or "").strip())
        if not compact:
            return None
        lowered = compact.lower()
        if any(term in lowered for term in OWNER_NARRATIVE_BANNED_TERMS):
            return None
        sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", compact) if segment.strip()]
        if len(sentences) < 3:
            return None
        if len(sentences) > 4:
            sentences = sentences[:4]
        normalized = " ".join(sentences)
        return normalized if normalized.endswith((".", "!", "?")) else f"{normalized}."

    def _build_owner_narrative_fallback(self, score_payload: Dict[str, Any]) -> str:
        score = int(score_payload.get("credit_score", 0))
        risk_band = self._normalize_risk_band_label(score_payload.get("risk_band", {}).get("band"))
        translated_reasons = [
            self._translate_reason_for_owner(reason)
            for reason in score_payload.get("top_reasons", [])
        ]
        top_reason = next(
            (reason for reason in translated_reasons if reason),
            "lenders still need to see a stronger and more stable business pattern",
        )

        counterfactual = score_payload.get("counterfactual_recommendations") or {}
        recommendations = counterfactual.get("recommendations") or []
        top_recommendation = recommendations[0] if recommendations else None
        trajectory = score_payload.get("score_trajectory") or {}
        lender_recommendations = score_payload.get("lender_recommendations") or {}
        recommended_lender = lender_recommendations.get("recommended_lender")
        closest_lender = lender_recommendations.get("closest_lender")

        second_sentence = (
            f"The single biggest move now is to {self._translate_recommendation_for_owner(top_recommendation)}, "
            f"which is expected to add about {top_recommendation['estimated_score_improvement']} points if you reach {top_recommendation['target_value_display']}."
            if top_recommendation
            else "The next step is to strengthen the business signals lenders can see every month."
        )
        third_sentence = (
            f"If you follow that plan, your score is projected to reach about {trajectory.get('target_score_day_90', score)} within 90 days."
        )
        fraud_sentence = self._owner_fraud_sentence(score_payload)
        if "no major circular payment warning" in fraud_sentence.lower():
            fourth_sentence = (
                f"That path keeps you on track for {recommended_lender['display_name']} lending, so your next step this week is to start with the first recommended action and stick to it consistently."
                if recommended_lender
                else f"You are not fully lender-ready yet, and {closest_lender['display_name']} is the nearest tier today, so your next step this week is to start with the first recommended action and build consistency."
                if closest_lender
                else "You are not lender-ready yet, so your next step this week is to start with the first recommended action and build consistency."
            )
        else:
            fourth_sentence = (
                f"{fraud_sentence} Your next step this week is to start with the first recommended action and fix that payment pattern alongside it."
            )

        sentences = [
            f"Your business is currently at {score}, which puts you in the {risk_band} range, and the main thing holding it back is that {top_reason}.",
            second_sentence,
            third_sentence,
        ]
        sentences.append(fourth_sentence)
        return " ".join(sentences[:4])

    def _build_anthropic_client(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if Anthropic is None or not api_key:
            return None
        return Anthropic(api_key=api_key)

    def _build_sources(self, *source_groups: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        similar_cases: List[Dict[str, Any]] = []
        rules_applied: List[Dict[str, Any]] = []
        guidelines_referenced: List[Dict[str, Any]] = []
        rbi_sections: List[str] = []

        seen_similar_cases = set()
        seen_rules = set()
        seen_guidelines = set()

        for group in source_groups:
            for item in group:
                item_id = item.get("id")
                collection = item.get("collection")
                metadata = item.get("metadata") or {}
                text = item.get("text") or item.get("summary") or ""

                if collection == "score_history" or item.get("credit_score") is not None:
                    gstin = str(item.get("gstin") or metadata.get("gstin") or "")
                    if not gstin or gstin in seen_similar_cases:
                        continue
                    seen_similar_cases.add(gstin)
                    outcome_payload = item.get("outcome") or {}
                    outcome_status = str(outcome_payload.get("status") or "pending").lower()
                    if outcome_status not in {"repaid", "defaulted", "pending"}:
                        outcome_status = "pending"
                    summary = self._build_similar_case_summary(item)
                    similar_cases.append(
                        {
                            "gstin": gstin,
                            "score": int(item.get("credit_score") or metadata.get("credit_score") or 0),
                            "outcome": outcome_status,
                            "similarityScore": float(item.get("similarity") or 0.0),
                            "existsInHistory": True,
                            "summary": summary,
                        }
                    )
                    continue

                doc_type = str(metadata.get("doc_type") or metadata.get("rule_type") or "")
                if collection == "rules" or doc_type in {"rbi_guideline", "industry_profile", "association_rule", "apriori_rule"}:
                    if doc_type in {"rbi_guideline", "industry_profile"}:
                        section = self._guideline_section_from_metadata(metadata)
                        guideline = {
                            "title": str(metadata.get("source") or metadata.get("industry_label") or "Guideline Reference"),
                            "section": section,
                            "excerpt": text,
                        }
                        guideline_key = (guideline["title"], guideline["section"])
                        if guideline_key not in seen_guidelines:
                            seen_guidelines.add(guideline_key)
                            guidelines_referenced.append(guideline)
                        if doc_type == "rbi_guideline" and section not in rbi_sections:
                            rbi_sections.append(section)
                        continue

                    rule_id = str(item_id or text)
                    if rule_id in seen_rules:
                        continue
                    seen_rules.add(rule_id)
                    rules_applied.append(
                        {
                            "antecedents": self._rule_antecedents(metadata, text),
                            "consequent": self._rule_consequent(metadata, text),
                            "confidence": self._rule_confidence(metadata, item.get("similarity")),
                            "support": self._rule_support(metadata),
                            "explanation": text,
                        }
                    )

        return {
            "similarCasesCount": len(similar_cases),
            "similarCases": similar_cases,
            "rulesApplied": rules_applied,
            "guidelinesReferenced": guidelines_referenced,
            "rbiGuidelineSections": rbi_sections,
        }

    def _structure_narrative(self, text: str) -> Dict[str, str]:
        paragraphs = [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
        if len(paragraphs) >= 3:
            overview, risks, recommendation = paragraphs[:3]
        else:
            sentences = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text.strip()) if segment.strip()]
            if len(sentences) >= 3:
                first_cut = max(1, len(sentences) // 3)
                second_cut = max(first_cut + 1, (2 * len(sentences)) // 3)
                overview = " ".join(sentences[:first_cut]).strip()
                risks = " ".join(sentences[first_cut:second_cut]).strip()
                recommendation = " ".join(sentences[second_cut:]).strip()
            else:
                overview = text.strip()
                risks = ""
                recommendation = ""
        return {
            "businessOverview": overview,
            "keyRiskFactors": risks,
            "recommendation": recommendation,
        }

    def _build_similar_case_summary(self, item: Dict[str, Any]) -> str:
        reasons = item.get("key_shap_reasons") or []
        if reasons:
            summaries = [reason.get("reason") for reason in reasons if reason.get("reason")]
            if summaries:
                return " ".join(summaries[:2])
        company_name = item.get("company_name")
        if company_name:
            return f"Comparable case from {company_name}."
        return "Similar historical business profile."

    def _guideline_section_from_metadata(self, metadata: Dict[str, Any]) -> str:
        if metadata.get("topic"):
            return str(metadata["topic"]).replace("_", " ").title()
        if metadata.get("industry_code"):
            return f"NIC {metadata['industry_code']}"
        return str(metadata.get("source") or "Reference")

    def _rule_antecedents(self, metadata: Dict[str, Any], text: str) -> List[str]:
        antecedents = metadata.get("antecedents")
        if isinstance(antecedents, str):
            try:
                parsed = json.loads(antecedents)
                if isinstance(parsed, list):
                    antecedents = parsed
            except Exception:
                antecedents = [antecedents]
        if isinstance(antecedents, list) and antecedents:
            return [str(item).replace("_", " ") for item in antecedents]
        hint = metadata.get("industry_hint") or metadata.get("topic") or metadata.get("industry_label")
        if hint:
            return [str(hint).replace("_", " ")]
        trimmed = text.split(".")[0].strip()
        return [trimmed[:80]] if trimmed else ["retrieved pattern"]

    def _rule_consequent(self, metadata: Dict[str, Any], text: str) -> str:
        consequent = str(metadata.get("consequent") or "").lower()
        if consequent in {"repaid", "defaulted"}:
            return consequent
        risk_direction = str(metadata.get("risk_direction") or "").lower()
        text_lower = text.lower()
        if risk_direction == "positive" or "repay" in text_lower or "lower-risk" in text_lower:
            return "repaid"
        return "defaulted"

    def _rule_confidence(self, metadata: Dict[str, Any], fallback_similarity: Any) -> float:
        raw = metadata.get("confidence")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = float(fallback_similarity or 0.0)
        return max(0.0, min(1.0, value))

    def _rule_support(self, metadata: Dict[str, Any]) -> float:
        try:
            value = float(metadata.get("support"))
        except (TypeError, ValueError):
            value = 0.0
        return max(0.0, min(1.0, value))


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return LLMService()
