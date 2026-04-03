"""
Sector / Macro Research Engine.
Runs structured sector-level, sub-sector, and macro-economic research queries.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class SectorReport:
    sector_name: str
    sector_outlook: str          # POSITIVE / NEUTRAL / NEGATIVE
    sector_growth_rate: str      # e.g. "14% YoY"
    sub_sector_analysis: str
    macro_indicators: List[str]
    risk_factors: List[str]
    regulatory_updates: List[str]
    data_sources: List[str]


# ── Demo sector data ──────────────────────────────────────────────
DEMO_SECTORS = {
    "Textiles — Spinning & Weaving": SectorReport(
        sector_name="Textiles — Spinning & Weaving",
        sector_outlook="NEUTRAL",
        sector_growth_rate="3% YoY",
        sub_sector_analysis=(
            "Indian textile spinning segment faces margin pressure from rising cotton prices "
            "(up 12% YoY) and cheaper synthetic imports. Weaving sub-sector shows flat growth. "
            "PLI scheme for technical textiles announced but adoption remains slow in traditional mills."
        ),
        macro_indicators=[
            "Cotton prices: ₹62,500/candy (up 12% YoY)",
            "Export demand: Moderate — EU orders stable, US orders declining 5%",
            "Domestic consumption: Growing at 4% driven by branded retail",
            "INR/USD: ₹83.2 — unfavorable for import-dependent units",
        ],
        risk_factors=[
            "Raw material price volatility (cotton, yarn)",
            "Labour-intensive sector with rising minimum wage pressures",
            "Competition from Bangladesh and Vietnam on unit cost",
            "Seasonality risk: monsoon-dependent raw material supply",
        ],
        regulatory_updates=[
            "RBI: No sector-specific NPA relaxation for textiles",
            "Ministry of Textiles: ₹10,683 Cr PLI scheme for MMF/technical textiles",
            "BIS: Mandatory quality standards for textile exports effective Jan 2025",
        ],
        data_sources=["Tavily", "RBI Sectoral Credit Data", "CMIE"],
    ),
    "Industrial Machinery — CNC & Automation": SectorReport(
        sector_name="Industrial Machinery — CNC & Automation",
        sector_outlook="POSITIVE",
        sector_growth_rate="14% YoY",
        sub_sector_analysis=(
            "CNC machinery and industrial automation sector is experiencing strong tailwinds. "
            "Defence indigenisation (Make in India) and Atmanirbhar Bharat driving domestic demand. "
            "EV manufacturing transition creating new CNC requirements. Order books healthy across leaders."
        ),
        macro_indicators=[
            "Industrial production index: Growing 6.2% YoY",
            "Capital goods imports: Declining 3% (positive for domestic manufacturers)",
            "Defence procurement: ₹1.72 Lakh Cr allocated (FY25), 75% reserved for domestic",
            "PLI for capital goods: ₹1,048 Cr approved across 58 companies",
        ],
        risk_factors=[
            "Supply chain risk on imported CNC controllers and servo drives",
            "Skilled labour shortage in precision machining",
            "Geopolitical disruption risk on semiconductor components",
        ],
        regulatory_updates=[
            "RBI: No adverse sector circular — stable regulatory environment",
            "DPIIT: 100% FDI under automatic route for manufacturing",
            "MSDE: National Apprenticeship Promotion Scheme expanded for capital goods sector",
        ],
        data_sources=["Tavily", "IMTMA Annual Report", "CMIE", "MoD Procurement Data"],
    ),
}


class SectorResearchEngine:
    """
    Provides structured sector/macro research context.
    Production: queries Tavily + structures via LLM.
    Prototype: returns demo-specific sector data.
    """

    def research(self, sector: str) -> SectorReport:
        """Returns sector research report. Falls back to generic if sector not found."""
        if sector in DEMO_SECTORS:
            return DEMO_SECTORS[sector]

        # Generic fallback
        return SectorReport(
            sector_name=sector,
            sector_outlook="NEUTRAL",
            sector_growth_rate="N/A",
            sub_sector_analysis=f"Detailed sub-sector analysis for {sector} pending external research.",
            macro_indicators=["GDP growth: 6.5% (FY25)", "Repo rate: 6.50%", "CPI inflation: 5.1%"],
            risk_factors=["Sector-specific risks to be assessed"],
            regulatory_updates=["No sector-specific RBI circulars identified"],
            data_sources=["Pending Tavily research"],
        )

    def to_dict(self, report: SectorReport) -> Dict:
        return {
            "sector_name": report.sector_name,
            "sector_outlook": report.sector_outlook,
            "sector_growth_rate": report.sector_growth_rate,
            "sub_sector_analysis": report.sub_sector_analysis,
            "macro_indicators": report.macro_indicators,
            "risk_factors": report.risk_factors,
            "regulatory_updates": report.regulatory_updates,
            "data_sources": report.data_sources,
        }
