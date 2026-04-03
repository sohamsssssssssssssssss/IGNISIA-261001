"""
LLM orchestration for underwriting narratives and stateful chat.
Uses Anthropic Claude Sonnet first and falls back to the local unified LLM client.
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

    def _generate_text(self, *, prompt: str, max_tokens: int, temperature: float) -> tuple[str, str]:
        if self.anthropic_client is not None:
            try:
                message = self.anthropic_client.messages.create(
                    model=ANTHROPIC_MODEL,
                    system=self.context_builder.get_system_prompt(),
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                blocks = []
                for block in getattr(message, "content", []):
                    text = getattr(block, "text", None)
                    if text:
                        blocks.append(text)
                text = "\n".join(blocks).strip()
                if text:
                    return text, ANTHROPIC_MODEL
            except Exception:
                pass

        fallback_prompt = (
            f"{self.context_builder.get_system_prompt()}\n\n"
            f"{prompt}\n\n"
            "If fraud is detected, flag it prominently. Do not make the final approval decision."
        )
        return self.fallback_llm.generate_sync(fallback_prompt, max_tokens=max_tokens), "fallback-llm"

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
