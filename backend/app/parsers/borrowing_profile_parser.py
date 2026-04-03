"""
Borrowing Profile Parser.
Extracts existing lender list, outstanding loans, repayment schedules, debt covenants.
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FacilityRecord:
    lender: str                 # e.g. "State Bank of India"
    facility_type: str          # e.g. "Term Loan", "CC/OD", "LC", "BG"
    sanctioned_limit: float     # INR Lakhs
    outstanding: float
    rate_of_interest: float     # e.g. 9.5
    maturity_date: Optional[str]
    overdue_amount: float
    is_npa: bool
    security_details: str


@dataclass
class DebtCovenant:
    covenant_name: str          # e.g. "Current Ratio", "TOL/TNW", "DSCR"
    threshold: str              # e.g. ">= 1.33"
    actual: str                 # e.g. "1.45"
    status: str                 # MET / BREACHED


@dataclass
class BorrowingProfile:
    company_name: str
    total_sanctioned: float
    total_outstanding: float
    total_overdue: float
    number_of_lenders: int
    consortium_flag: bool
    npa_facilities: int
    utilization_pct: float
    debt_concentration_risk: str   # LOW / MODERATE / HIGH
    facilities: List[FacilityRecord] = field(default_factory=list)
    covenants: List[DebtCovenant] = field(default_factory=list)


class BorrowingProfileParser:
    """Parses borrowing profile / consortium exposure summary."""

    @staticmethod
    def parse_csv(file_path: str, company_name: str = "N/A") -> BorrowingProfile:
        df = pd.read_csv(file_path)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        lender_col = next((c for c in df.columns if "lender" in c or "bank" in c or "institution" in c), df.columns[0])
        type_col = next((c for c in df.columns if "type" in c or "facility" in c), None)
        sanct_col = next((c for c in df.columns if "sanction" in c or "limit" in c), None)
        outst_col = next((c for c in df.columns if "outstand" in c or "balance" in c or "utilized" in c), None)
        rate_col = next((c for c in df.columns if "rate" in c or "interest" in c or "roi" in c), None)
        overdue_col = next((c for c in df.columns if "overdue" in c or "arrear" in c), None)
        npa_col = next((c for c in df.columns if "npa" in c or "classification" in c), None)

        facilities = []
        total_sanct = 0.0
        total_outst = 0.0
        total_overdue = 0.0
        npa_count = 0
        lenders = set()

        for _, row in df.iterrows():
            lender = str(row[lender_col]).strip()
            lenders.add(lender)
            sanctioned = float(row[sanct_col]) if sanct_col and pd.notnull(row[sanct_col]) else 0.0
            outstanding = float(row[outst_col]) if outst_col and pd.notnull(row[outst_col]) else 0.0
            rate = float(row[rate_col]) if rate_col and pd.notnull(row[rate_col]) else 0.0
            overdue = float(row[overdue_col]) if overdue_col and pd.notnull(row[overdue_col]) else 0.0
            is_npa = str(row[npa_col]).strip().upper() in ("YES", "NPA", "TRUE", "1") if npa_col and pd.notnull(row[npa_col]) else False

            total_sanct += sanctioned
            total_outst += outstanding
            total_overdue += overdue
            if is_npa:
                npa_count += 1

            facilities.append(FacilityRecord(
                lender=lender,
                facility_type=str(row[type_col]).strip() if type_col and pd.notnull(row[type_col]) else "N/A",
                sanctioned_limit=sanctioned,
                outstanding=outstanding,
                rate_of_interest=rate,
                maturity_date=None,
                overdue_amount=overdue,
                is_npa=is_npa,
                security_details="",
            ))

        utilization = round(total_outst / total_sanct * 100, 2) if total_sanct else 0.0

        # Concentration: if top lender > 60% of total exposure → HIGH
        lender_exposures = {}
        for f in facilities:
            lender_exposures[f.lender] = lender_exposures.get(f.lender, 0) + f.outstanding
        max_exposure_pct = (max(lender_exposures.values()) / total_outst * 100) if total_outst else 0
        if max_exposure_pct > 60 or npa_count > 0:
            conc_risk = "HIGH"
        elif max_exposure_pct > 40:
            conc_risk = "MODERATE"
        else:
            conc_risk = "LOW"

        return BorrowingProfile(
            company_name=company_name,
            total_sanctioned=total_sanct,
            total_outstanding=total_outst,
            total_overdue=total_overdue,
            number_of_lenders=len(lenders),
            consortium_flag=len(lenders) > 1,
            npa_facilities=npa_count,
            utilization_pct=utilization,
            debt_concentration_risk=conc_risk,
            facilities=facilities,
        )


def parse_borrowing_profile(file_path: str, company_name: str = "N/A") -> BorrowingProfile:
    """Backward-compatible helper used by API routes."""
    if file_path.lower().endswith(".csv"):
        return BorrowingProfileParser.parse_csv(file_path, company_name=company_name)
    raise ValueError(f"Unsupported borrowing profile file format for {file_path}")
