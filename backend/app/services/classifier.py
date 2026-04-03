"""
Document Classifier — Auto-classifies uploaded files and supports HITL review.
Uses filename heuristics + content-based keyword detection.
"""

from dataclasses import dataclass
from typing import Optional
import re


DOC_TYPES = [
    "ALM",
    "SHAREHOLDING_PATTERN",
    "BORROWING_PROFILE",
    "ANNUAL_REPORT",
    "PORTFOLIO_CUTS",
]

# Keyword → doc_type mapping (priority-ordered)
KEYWORD_MAP = {
    "ALM": [
        "asset liability", "maturity bucket", "liquidity gap", "structural liquidity",
        "alm", "interest rate risk", "funding mismatch", "repricing gap",
    ],
    "SHAREHOLDING_PATTERN": [
        "shareholding pattern", "promoter holding", "fii", "dii", "pledge",
        "encumbered", "public shareholding", "sebi", "category of shareholder",
    ],
    "BORROWING_PROFILE": [
        "borrowing profile", "consortium", "sanctioned limit", "outstanding",
        "lender", "facility", "term loan", "working capital", "cc/od",
        "debt covenant", "repayment schedule",
    ],
    "ANNUAL_REPORT": [
        "annual report", "balance sheet", "profit and loss", "p&l", "cash flow",
        "director's report", "auditor's report", "schedule", "notes to accounts",
        "financial statements",
    ],
    "PORTFOLIO_CUTS": [
        "portfolio", "npa", "vintage", "collection efficiency", "loan book",
        "provision coverage", "gross npa", "net npa", "write-off", "aum",
        "product cut", "delinquency",
    ],
}

# Filename pattern → doc_type
FILENAME_PATTERNS = {
    r"alm|asset.?liab": "ALM",
    r"sharehold|shp|sebi": "SHAREHOLDING_PATTERN",
    r"borrow|consortium|facilit|lender": "BORROWING_PROFILE",
    r"annual.?report|p.?l|balance.?sheet|financial|audit": "ANNUAL_REPORT",
    r"portfolio|npa|vintage|collection|loan.?book": "PORTFOLIO_CUTS",
}


@dataclass
class ClassificationResult:
    predicted_type: str
    confidence: float       # 0.0 - 1.0
    evidence: str           # Why we think this
    filename: str
    status: str = "PENDING"  # PENDING → APPROVED / EDITED / REJECTED


class DocumentClassifier:
    """Auto-classifies uploaded documents into one of the 5 required types."""

    def auto_classify(self, filename: str, text_sample: str) -> ClassificationResult:
        """
        Step 1: Filename heuristics (fast, high confidence on good filenames).
        Step 2: Content keyword scan (keyword density).
        """
        filename_lower = filename.lower()

        # ── Step 1: Filename matching ──────────────────────────────
        for pattern, doc_type in FILENAME_PATTERNS.items():
            if re.search(pattern, filename_lower):
                return ClassificationResult(
                    predicted_type=doc_type,
                    confidence=0.85,
                    evidence=f"Filename '{filename}' matches pattern for {doc_type}",
                    filename=filename,
                )

        # ── Step 2: Content keyword scan ──────────────────────────
        text_sample = text_sample.lower()

        scores = {}
        for doc_type, keywords in KEYWORD_MAP.items():
            hits = sum(1 for kw in keywords if kw in text_sample)
            scores[doc_type] = hits

        if scores:
            best_type = max(scores, key=scores.get)
            best_score = scores[best_type]
            total_keywords = len(KEYWORD_MAP[best_type])
            confidence = min(best_score / max(total_keywords * 0.4, 1), 1.0)

            if best_score > 0:
                return ClassificationResult(
                    predicted_type=best_type,
                    confidence=round(confidence, 2),
                    evidence=f"Content scan: {best_score} keyword matches for {best_type}",
                    filename=filename,
                )

        # ── Fallback ──────────────────────────────────────────────
        return ClassificationResult(
            predicted_type="ANNUAL_REPORT",  # safest default
            confidence=0.3,
            evidence="Low confidence — manual classification recommended",
            filename=filename,
        )
