"""
Portfolio Cuts / Performance Data Parser.
Extracts loan book quality, NPA %, collection efficiency, vintage curves.
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VintageBucket:
    vintage: str                # e.g. "0-6 months", "6-12 months"
    principal_outstanding: float
    npa_amount: float
    npa_pct: float
    collection_efficiency: float   # 0-100%
    write_off_amount: float


@dataclass
class ProductCut:
    product_name: str           # e.g. "Term Loan", "CC/OD", "Gold Loan"
    aum: float                  # Assets Under Management (INR Lakhs)
    gross_npa_pct: float
    net_npa_pct: float
    provision_coverage: float   # %
    yield_pct: float


@dataclass
class PortfolioReport:
    company_name: str
    report_date: str
    total_aum: float
    gross_npa_pct: float
    net_npa_pct: float
    provision_coverage_ratio: float
    overall_collection_efficiency: float
    portfolio_risk: str          # LOW / MODERATE / HIGH
    vintages: List[VintageBucket] = field(default_factory=list)
    product_cuts: List[ProductCut] = field(default_factory=list)


class PortfolioParser:
    """Parses portfolio quality / performance data (CSV format)."""

    @staticmethod
    def parse_csv(file_path: str, company_name: str = "N/A") -> PortfolioReport:
        df = pd.read_csv(file_path)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Detect whether this is vintage data or product-cut data
        is_vintage = any("vintage" in c or "age" in c or "bucket" in c for c in df.columns)
        is_product = any("product" in c or "segment" in c or "scheme" in c for c in df.columns)

        vintages = []
        product_cuts = []
        total_aum = 0.0
        weighted_npa = 0.0
        weighted_collection = 0.0

        if is_vintage:
            bucket_col = next((c for c in df.columns if "vintage" in c or "age" in c or "bucket" in c), df.columns[0])
            prin_col = next((c for c in df.columns if "principal" in c or "outstanding" in c or "aum" in c), None)
            npa_col = next((c for c in df.columns if "npa" in c), None)
            coll_col = next((c for c in df.columns if "collection" in c or "recovery" in c), None)

            for _, row in df.iterrows():
                principal = float(row[prin_col]) if prin_col and pd.notnull(row[prin_col]) else 0.0
                npa_amt = float(row[npa_col]) if npa_col and pd.notnull(row[npa_col]) else 0.0
                npa_pct = (npa_amt / principal * 100) if principal else 0.0
                coll_eff = float(row[coll_col]) if coll_col and pd.notnull(row[coll_col]) else 100.0
                total_aum += principal

                vintages.append(VintageBucket(
                    vintage=str(row[bucket_col]),
                    principal_outstanding=principal,
                    npa_amount=npa_amt,
                    npa_pct=round(npa_pct, 2),
                    collection_efficiency=coll_eff,
                    write_off_amount=0.0,
                ))

        if is_product:
            prod_col = next((c for c in df.columns if "product" in c or "segment" in c or "scheme" in c), df.columns[0])
            aum_col = next((c for c in df.columns if "aum" in c or "outstanding" in c), None)
            gnpa_col = next((c for c in df.columns if "gross" in c and "npa" in c), None)
            nnpa_col = next((c for c in df.columns if "net" in c and "npa" in c), None)

            for _, row in df.iterrows():
                aum = float(row[aum_col]) if aum_col and pd.notnull(row[aum_col]) else 0.0
                gnpa = float(row[gnpa_col]) if gnpa_col and pd.notnull(row[gnpa_col]) else 0.0
                nnpa = float(row[nnpa_col]) if nnpa_col and pd.notnull(row[nnpa_col]) else 0.0
                if not is_vintage:
                    total_aum += aum
                weighted_npa += gnpa * aum

                product_cuts.append(ProductCut(
                    product_name=str(row[prod_col]),
                    aum=aum,
                    gross_npa_pct=gnpa,
                    net_npa_pct=nnpa,
                    provision_coverage=round((gnpa - nnpa) / gnpa * 100, 1) if gnpa else 100.0,
                    yield_pct=0.0,
                ))

        gross_npa = round(weighted_npa / total_aum, 2) if total_aum and weighted_npa else (
            sum(v.npa_pct * v.principal_outstanding for v in vintages) / total_aum if total_aum and vintages else 0.0
        )
        overall_coll = (sum(v.collection_efficiency * v.principal_outstanding for v in vintages) / total_aum) if total_aum and vintages else 95.0

        if gross_npa > 5 or overall_coll < 85:
            risk = "HIGH"
        elif gross_npa > 2 or overall_coll < 92:
            risk = "MODERATE"
        else:
            risk = "LOW"

        return PortfolioReport(
            company_name=company_name,
            report_date="FY24",
            total_aum=total_aum,
            gross_npa_pct=round(gross_npa, 2),
            net_npa_pct=round(gross_npa * 0.6, 2),   # simplified
            provision_coverage_ratio=round((gross_npa - gross_npa * 0.6) / gross_npa * 100, 1) if gross_npa else 100.0,
            overall_collection_efficiency=round(overall_coll, 1),
            portfolio_risk=risk,
            vintages=vintages,
            product_cuts=product_cuts,
        )


def parse_portfolio_cuts(file_path: str, company_name: str = "N/A") -> PortfolioReport:
    """Backward-compatible helper used by API routes."""
    if file_path.lower().endswith(".csv"):
        return PortfolioParser.parse_csv(file_path, company_name=company_name)
    raise ValueError(f"Unsupported portfolio file format for {file_path}")
