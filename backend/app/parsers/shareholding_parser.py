"""
Shareholding Pattern Parser.
Extracts promoter holding %, pledge data, FII/DII breakdown, ownership structure.
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ShareholderCategory:
    category: str           # e.g. "Promoter & Promoter Group", "FII", "DII", "Public"
    holding_pct: float
    shares: int
    pledged_pct: float      # % of shares pledged (relevant for promoters)
    encumbered_pct: float


@dataclass
class ShareholdingReport:
    company_name: str
    report_quarter: str     # e.g. "Q3 FY24"
    total_shares: int
    promoter_holding_pct: float
    promoter_pledged_pct: float
    fii_holding_pct: float
    dii_holding_pct: float
    public_holding_pct: float
    concentration_risk: str   # LOW / MODERATE / HIGH
    categories: List[ShareholderCategory] = field(default_factory=list)


class ShareholdingParser:
    """Parses SEBI-format shareholding pattern disclosures."""

    @staticmethod
    def parse_csv(file_path: str, company_name: str = "N/A") -> ShareholdingReport:
        df = pd.read_csv(file_path)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        cat_col = next((c for c in df.columns if "category" in c or "holder" in c), df.columns[0])
        pct_col = next((c for c in df.columns if "percent" in c or "pct" in c or "holding" in c), None)
        shares_col = next((c for c in df.columns if "shares" in c or "quantity" in c), None)
        pledge_col = next((c for c in df.columns if "pledge" in c or "encumb" in c), None)

        if not pct_col:
            raise ValueError("Shareholding CSV must contain a percentage/holding column")

        categories = []
        totals = {"promoter": 0, "fii": 0, "dii": 0, "public": 0}
        promoter_pledge = 0.0
        total_shares = 0

        for _, row in df.iterrows():
            cat_name = str(row[cat_col]).strip()
            holding = float(row[pct_col]) if pd.notnull(row[pct_col]) else 0.0
            shares = int(row[shares_col]) if shares_col and pd.notnull(row[shares_col]) else 0
            pledged = float(row[pledge_col]) if pledge_col and pd.notnull(row[pledge_col]) else 0.0
            total_shares += shares

            cat_lower = cat_name.lower()
            if "promoter" in cat_lower:
                totals["promoter"] += holding
                promoter_pledge = max(promoter_pledge, pledged)
            elif "fii" in cat_lower or "foreign" in cat_lower or "fpi" in cat_lower:
                totals["fii"] += holding
            elif "dii" in cat_lower or "mutual" in cat_lower or "domestic" in cat_lower or "insurance" in cat_lower:
                totals["dii"] += holding
            else:
                totals["public"] += holding

            categories.append(ShareholderCategory(
                category=cat_name,
                holding_pct=holding,
                shares=shares,
                pledged_pct=pledged,
                encumbered_pct=pledged,
            ))

        # Concentration risk assessment
        if totals["promoter"] > 75 or promoter_pledge > 50:
            conc_risk = "HIGH"
        elif totals["promoter"] > 60 or promoter_pledge > 20:
            conc_risk = "MODERATE"
        else:
            conc_risk = "LOW"

        return ShareholdingReport(
            company_name=company_name,
            report_quarter="Q3 FY24",
            total_shares=total_shares,
            promoter_holding_pct=round(totals["promoter"], 2),
            promoter_pledged_pct=round(promoter_pledge, 2),
            fii_holding_pct=round(totals["fii"], 2),
            dii_holding_pct=round(totals["dii"], 2),
            public_holding_pct=round(totals["public"], 2),
            concentration_risk=conc_risk,
            categories=categories,
        )


def parse_shareholding(file_path: str, company_name: str = "N/A") -> ShareholdingReport:
    """Backward-compatible helper used by API routes."""
    if file_path.lower().endswith(".csv"):
        return ShareholdingParser.parse_csv(file_path, company_name=company_name)
    raise ValueError(f"Unsupported shareholding file format for {file_path}")
