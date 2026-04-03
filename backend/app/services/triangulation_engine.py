"""
Triangulation Engine — Cross-references external research with internal document data.
Bridges Gap 7: explicitly connecting web-scraped findings with extracted document data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class TriangulationFinding:
    external_signal: str      # What external research says
    internal_data_point: str  # What the uploaded documents say
    alignment: str            # ALIGNED / CONTRADICTED / UNVERIFIED
    severity: str             # INFO / WARN / CRIT
    recommendation: str


@dataclass
class TriangulationReport:
    total_checks: int
    aligned: int
    contradicted: int
    unverified: int
    findings: List[TriangulationFinding] = field(default_factory=list)


# ── Demo triangulation data ───────────────────────────────────────
DEMO_TRIANGULATION = {
    "reject": TriangulationReport(
        total_checks=5,
        aligned=1,
        contradicted=3,
        unverified=1,
        findings=[
            TriangulationFinding(
                external_signal="eCourts: Active DRT case DRT/MUM/2024/1847 — ₹45L disputed",
                internal_data_point="Annual Report: No mention of contingent liabilities or pending cases",
                alignment="CONTRADICTED",
                severity="CRIT",
                recommendation="AR likely omits material litigation. Flag for non-disclosure under IndAS 37."
            ),
            TriangulationFinding(
                external_signal="MCA: Director Arjun Singhania linked to 2 NPA-classified entities",
                internal_data_point="Shareholding: Promoter holding 72% with no related-party disclosure",
                alignment="CONTRADICTED",
                severity="CRIT",
                recommendation="Shell entity linkages not disclosed. Request full related-party transaction schedule."
            ),
            TriangulationFinding(
                external_signal="News: 'Textile unit faces labour dispute' (Feb 2025)",
                internal_data_point="Bank Statement: Salary credits show 30% decline in Jan-Feb 2025",
                alignment="ALIGNED",
                severity="WARN",
                recommendation="Labour dispute corroborated by declining salary payments. Operational risk elevated."
            ),
            TriangulationFinding(
                external_signal="Sector NPA rate for textiles: 8.2% (RBI Q3 data)",
                internal_data_point="CIBIL CMR-6 score with GSTR ITC mismatch of 18%",
                alignment="CONTRADICTED",
                severity="WARN",
                recommendation="Borrower's risk profile significantly worse than sector average. Reject or restructure."
            ),
            TriangulationFinding(
                external_signal="Cotton prices up 12% YoY — margin pressure expected",
                internal_data_point="No recent commodity hedging visible in bank transactions",
                alignment="UNVERIFIED",
                severity="INFO",
                recommendation="Request commodity hedging policy and exposure schedule."
            ),
        ]
    ),
    "approve": TriangulationReport(
        total_checks=5,
        aligned=4,
        contradicted=0,
        unverified=1,
        findings=[
            TriangulationFinding(
                external_signal="eCourts: Zero litigation for CleanTech Manufacturing or Vikram Mehta",
                internal_data_point="Annual Report: 'No contingent liabilities' — IndAS 37 compliant",
                alignment="ALIGNED",
                severity="INFO",
                recommendation="Clean legal record confirmed across external and internal sources."
            ),
            TriangulationFinding(
                external_signal="News: 'CleanTech wins ₹8Cr defence order' (Jan 2025)",
                internal_data_point="Bank Statement: ₹2.1Cr advance received in Feb 2025",
                alignment="ALIGNED",
                severity="INFO",
                recommendation="Order win corroborated by bank inflow. Positive for cash flow projections."
            ),
            TriangulationFinding(
                external_signal="CNC sector growth: 14% YoY (IMTMA data)",
                internal_data_point="GST revenue growth: 11% YoY from GSTR-3B filings",
                alignment="ALIGNED",
                severity="INFO",
                recommendation="Borrower growing slightly below sector but within healthy range."
            ),
            TriangulationFinding(
                external_signal="MCA: Director Vikram Mehta — no linked NPA entities",
                internal_data_point="Shareholding: 67% promoter holding, zero pledge",
                alignment="ALIGNED",
                severity="INFO",
                recommendation="Clean promoter profile. Strong governance indicators."
            ),
            TriangulationFinding(
                external_signal="Semiconductor supply chain disruption risk (global)",
                internal_data_point="Borrowing profile does not show hedging or diversification",
                alignment="UNVERIFIED",
                severity="WARN",
                recommendation="Recommend discussing supply chain diversification strategy with promoter."
            ),
        ]
    ),
}


class TriangulationEngine:
    """
    Cross-references external research findings with internal extracted data.
    Production: runs structured comparisons between WebRAGAgent output and parsed documents.
    Prototype: returns demo-specific triangulation data.
    """

    def triangulate(
        self,
        web_findings: List[str] = None,
        contradictions: List[Any] = None,
        risk_flags: List[Any] = None,
        scenario: str = "approve",
    ) -> TriangulationReport:
        if scenario in DEMO_TRIANGULATION:
            return DEMO_TRIANGULATION[scenario]

        return TriangulationReport(
            total_checks=0, aligned=0, contradicted=0, unverified=0, findings=[]
        )

    def to_dict(self, report: TriangulationReport) -> Dict:
        return {
            "total_checks": report.total_checks,
            "aligned": report.aligned,
            "contradicted": report.contradicted,
            "unverified": report.unverified,
            "findings": [
                {
                    "external_signal": f.external_signal,
                    "internal_data_point": f.internal_data_point,
                    "alignment": f.alignment,
                    "severity": f.severity,
                    "recommendation": f.recommendation,
                }
                for f in report.findings
            ]
        }
