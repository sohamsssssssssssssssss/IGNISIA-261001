"""
ALM (Asset-Liability Management) Parser.
Extracts maturity buckets, liquidity gaps, interest rate risk, and funding mismatches.
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class MaturityBucket:
    bucket_label: str          # e.g. "1-7 days", "8-14 days", ...
    assets: float              # INR Lakhs
    liabilities: float
    gap: float                 # assets - liabilities
    cumulative_gap: float
    gap_pct: float             # gap / total assets %


@dataclass
class ALMReport:
    report_date: str
    total_assets: float
    total_liabilities: float
    net_gap: float
    negative_bucket_count: int
    interest_rate_risk: str    # LOW / MODERATE / HIGH
    liquidity_coverage_ratio: Optional[float]
    buckets: List[MaturityBucket] = field(default_factory=list)


STANDARD_BUCKETS = [
    "1-7 days", "8-14 days", "15-28 days", "29 days - 3 months",
    "3-6 months", "6 months - 1 year", "1-3 years", "3-5 years", "Over 5 years"
]


class ALMParser:
    """Parses ALM structural liquidity statements (CSV or Excel)."""

    @staticmethod
    def parse_csv(file_path: str) -> ALMReport:
        df = pd.read_csv(file_path)

        # Normalize column names
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        bucket_col = next((c for c in df.columns if "bucket" in c or "maturity" in c or "period" in c), df.columns[0])
        asset_col = next((c for c in df.columns if "asset" in c or "inflow" in c), None)
        liab_col = next((c for c in df.columns if "liab" in c or "outflow" in c), None)

        if not asset_col or not liab_col:
            raise ValueError("ALM CSV must contain asset/inflow and liability/outflow columns")

        total_assets = float(df[asset_col].sum())
        total_liabilities = float(df[liab_col].sum())
        cumulative = 0.0
        buckets = []

        for _, row in df.iterrows():
            assets = float(row[asset_col]) if pd.notnull(row[asset_col]) else 0.0
            liabilities = float(row[liab_col]) if pd.notnull(row[liab_col]) else 0.0
            gap = assets - liabilities
            cumulative += gap
            gap_pct = (gap / total_assets * 100) if total_assets else 0.0

            buckets.append(MaturityBucket(
                bucket_label=str(row[bucket_col]),
                assets=assets,
                liabilities=liabilities,
                gap=gap,
                cumulative_gap=cumulative,
                gap_pct=round(gap_pct, 2)
            ))

        negative_buckets = sum(1 for b in buckets if b.gap < 0)
        short_term_neg = sum(1 for b in buckets[:4] if b.gap < 0)

        if short_term_neg >= 2:
            ir_risk = "HIGH"
        elif negative_buckets >= 3:
            ir_risk = "MODERATE"
        else:
            ir_risk = "LOW"

        return ALMReport(
            report_date="FY24",
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_gap=total_assets - total_liabilities,
            negative_bucket_count=negative_buckets,
            interest_rate_risk=ir_risk,
            liquidity_coverage_ratio=round(total_assets / total_liabilities, 2) if total_liabilities else None,
            buckets=buckets,
        )


def parse_alm(file_path: str) -> ALMReport:
    """
    Backward-compatible helper used by API routes.
    Currently supports CSV inputs; Excel can be added later if needed.
    """
    if file_path.lower().endswith(".csv"):
        return ALMParser.parse_csv(file_path)
    raise ValueError(f"Unsupported ALM file format for {file_path}")
