"""
SWOT Analysis Engine — Generates structured SWOT using LLM grounded on extracted data.
"""

import json
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class SWOTResult:
    strengths: List[str]
    weaknesses: List[str]
    opportunities: List[str]
    threats: List[str]


# ── Hardcoded SWOT for demo scenarios ─────────────────────────────
DEMO_SWOT = {
    "reject": SWOTResult(
        strengths=[
            "Established presence in textile spinning & weaving segment (5-year vintage)",
            "Factory infrastructure with existing production capacity",
        ],
        weaknesses=[
            "Severe 3-way revenue mismatch: GST ₹12Cr vs Bank ₹4Cr vs AR ₹18Cr (67% gap)",
            "Active DRT litigation of ₹45L with ongoing proceedings (DRT/MUM/2024/1847)",
            "CIBIL CMR-6 — below institutional risk appetite threshold",
            "Director linked to 2 NPA-classified shell entities via MCA records",
            "GSTR 2A/3B ITC variance of 18% — potential circular trading indicator",
        ],
        opportunities=[
            "Textile sector showing 3% YoY growth nationally despite headwinds",
            "Government PLI scheme for technical textiles could improve margins if adopted",
        ],
        threats=[
            "Negative press: labour dispute reported (Feb 2025) signals operational instability",
            "Rising raw material costs (cotton prices up 12% YoY) pressuring margins",
            "Shell entity linkages expose promoter to potential ED/SFIO investigations",
            "RBI increased risk weight on unsecured commercial loans to 150%",
        ],
    ),
    "approve": SWOTResult(
        strengths=[
            "Revenue consistency: GST (₹41.8Cr), Bank (₹42.1Cr), AR (₹42.5Cr) within 2% tolerance",
            "CIBIL CMR-3 rating — strong institutional credit discipline",
            "Zero litigation: clean eCourts/DRT record, no adverse MCA flags",
            "DSCR of 1.8x — well above the 1.25x institutional threshold",
            "Strong collateral: SCR 1.6x with SARFAESI-enforceable security",
            "Promoter equity stake at 67% shows significant skin-in-the-game",
        ],
        weaknesses=[
            "Single-bank dependency for working capital (concentration risk)",
            "Promoter concentration at 67% — key-man risk if succession planning is weak",
        ],
        opportunities=[
            "CNC & Automation sector growing at 14% YoY nationally",
            "Recent ₹8Cr defence order win opens high-margin government contracting pipeline",
            "Make in India & Atmanirbhar Bharat incentives for indigenous machinery manufacturing",
        ],
        threats=[
            "Geopolitical supply chain disruption risk on imported CNC components",
            "Rising interest rate environment may increase cost of capital",
            "Foreign competitors with lower pricing entering Indian market",
        ],
    ),
}


class SWOTEngine:
    """
    Generates a structured SWOT analysis using pre-computed concept data.
    For prototype: returns demo-specific SWOT. 
    Production: calls Ollama/Groq with RAG context.
    """

    def generate_swot(
        self,
        concept_scores: Dict[str, float],
        shap_factors: List[Dict],
        contradictions: List[Any] = None,
        risk_flags: List[Any] = None,
        scenario: str = "approve",
    ) -> SWOTResult:
        """
        Returns SWOT grounded on quantitative data.
        In production, this would call the LLM with the pre-computed data.
        """
        if scenario in DEMO_SWOT:
            return DEMO_SWOT[scenario]

        # Fallback: generate from scores
        return self._generate_from_scores(concept_scores, shap_factors)

    def _generate_from_scores(self, scores: Dict, shap: List[Dict]) -> SWOTResult:
        strengths = []
        weaknesses = []

        for concept, score in scores.items():
            if score >= 0.75:
                strengths.append(f"Strong {concept} score ({score*100:.0f}%)")
            elif score < 0.50:
                weaknesses.append(f"Weak {concept} score ({score*100:.0f}%) — needs attention")

        positive_shap = [f["feature"] for f in shap if f.get("value", f.get("contribution", 0)) > 0]
        negative_shap = [f["feature"] for f in shap if f.get("value", f.get("contribution", 0)) < 0]

        return SWOTResult(
            strengths=strengths or ["No significant strengths identified"],
            weaknesses=weaknesses or ["No significant weaknesses identified"],
            opportunities=["Sector-specific opportunities to be assessed by analyst"],
            threats=[f"Risk factor: {f}" for f in negative_shap[:3]] or ["No immediate threats identified"],
        )

    def to_dict(self, result: SWOTResult) -> Dict:
        return {
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "opportunities": result.opportunities,
            "threats": result.threats,
        }
