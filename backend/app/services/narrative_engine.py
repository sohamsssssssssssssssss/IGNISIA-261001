"""
Narrative Engine — generates CAM prose sections using the unified LLM client.
Falls back gracefully: Ollama → Groq → template.
"""

import json
from typing import Dict, Any
from .llm_client import llm


class NarrativeEngine:
    """
    Generates the CAM's narrative prose sections.
    Takes pre-computed concept values as rigid JSON inputs to avoid hallucination on figures.
    """

    async def generate_cam_narrative(self, concept_scores: Dict[str, float], shap_factors: list) -> str:
        prompt = f"""You are an expert Indian Corporate Credit Analyst.
Please write a brief qualitative narrative for a Credit Appraisal Memo based ONLY on the following pre-computed data.
DO NOT invent or hallucinate any numbers. Explain the risk profile according to these ML concepts.

Concept Scores (0-1, where 1 is highest risk):
{json.dumps(concept_scores, indent=2)}

Top SHAP Drivers:
{json.dumps(shap_factors, indent=2)}

Return exactly 3 paragraphs:
1. Executive Summary
2. Key Risks
3. Financial Stability Outlook."""

        return await llm.generate(prompt, max_tokens=800)

    async def generate_devils_advocate(self, verdict: str, concept_scores: Dict[str, float],
                                        mgmt_quality: int, factory_utilisation: int) -> str:
        prompt = f"""You are a Devil's Advocate AI challenging a credit officer's assessment.
The AI verdict is {verdict}. The credit officer has set Management Quality to {mgmt_quality}/5
and Factory Utilisation to {factory_utilisation}%.

Concept scores: {json.dumps(concept_scores, indent=2)}

In 2-3 sentences, challenge the assessment. Ask probing questions about the weakest dimension.
Be specific and cite the data points."""

        return await llm.generate(prompt, max_tokens=300)
