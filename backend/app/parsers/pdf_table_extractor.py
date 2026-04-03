"""
PDF Table Extractor — uses pdfplumber for real financial table extraction.
Handles: Annual Reports, ALM statements, Shareholding patterns, and any PDF with tables.
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


@dataclass
class ExtractedTable:
    page_num: int
    headers: List[str]
    rows: List[List[str]]
    table_type: str = "unknown"  # detected type: pl, bs, cf, alm, shareholding, etc.


@dataclass
class PDFExtractionResult:
    filename: str
    total_pages: int
    tables: List[ExtractedTable]
    raw_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# Keyword maps for auto-detecting table purpose
TABLE_TYPE_KEYWORDS = {
    "pl": ["revenue", "sales", "ebitda", "pat", "profit", "loss", "income", "expenditure", "operating"],
    "bs": ["assets", "liabilities", "equity", "net worth", "reserves", "borrowings", "current assets"],
    "cf": ["cash flow", "operating activities", "investing", "financing", "net cash"],
    "alm": ["maturity", "bucket", "1-7 days", "8-14", "liquidity", "gap", "cumulative"],
    "shareholding": ["promoter", "fii", "dii", "public", "shares", "holding", "pledge"],
    "borrowing": ["lender", "outstanding", "facility", "sanctioned", "utilisation", "npa"],
    "portfolio": ["vintage", "npa", "collection", "aum", "product", "gross npa", "net npa"],
}


def _detect_table_type(headers: List[str], first_rows: List[List[str]]) -> str:
    """Auto-detect table type from header + first row content."""
    combined = " ".join(headers + [cell for row in first_rows[:3] for cell in row]).lower()
    best_type = "unknown"
    best_score = 0
    for ttype, keywords in TABLE_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_type = ttype
    return best_type if best_score >= 2 else "unknown"


def extract_tables_from_pdf(pdf_path: str) -> PDFExtractionResult:
    """
    Extract all tables from a PDF file using pdfplumber.
    Returns structured tables + raw text fallback.
    """
    if not HAS_PDFPLUMBER:
        # Fallback: extract raw text using basic file reading
        return PDFExtractionResult(
            filename=os.path.basename(pdf_path),
            total_pages=0,
            tables=[],
            raw_text=f"[pdfplumber not installed — raw extraction unavailable for {pdf_path}]",
            metadata={"error": "pdfplumber not installed"}
        )

    tables: List[ExtractedTable] = []
    raw_text_parts: List[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, 1):
            # Extract text
            page_text = page.extract_text() or ""
            if page_text.strip():
                raw_text_parts.append(f"--- Page {page_num} ---\n{page_text}")

            # Extract tables
            page_tables = page.extract_tables()
            for raw_table in page_tables:
                if not raw_table or len(raw_table) < 2:
                    continue

                # Clean cells
                cleaned = []
                for row in raw_table:
                    cleaned.append([str(cell).strip() if cell else "" for cell in row])

                headers = cleaned[0]
                rows = cleaned[1:]

                table_type = _detect_table_type(headers, rows)

                tables.append(ExtractedTable(
                    page_num=page_num,
                    headers=headers,
                    rows=rows,
                    table_type=table_type,
                ))

    return PDFExtractionResult(
        filename=os.path.basename(pdf_path),
        total_pages=total_pages,
        tables=tables,
        raw_text="\n\n".join(raw_text_parts),
        metadata={
            "tables_found": len(tables),
            "table_types": list(set(t.table_type for t in tables)),
        }
    )


def tables_to_structured_data(extraction: PDFExtractionResult) -> Dict[str, Any]:
    """
    Convert extracted tables to structured key-value data for downstream consumption.
    Returns a dict with detected table types as keys.
    """
    result: Dict[str, Any] = {
        "filename": extraction.filename,
        "pages": extraction.total_pages,
        "tables_found": len(extraction.tables),
        "data": {},
        "raw_text_preview": extraction.raw_text[:2000] if extraction.raw_text else "",
    }

    for table in extraction.tables:
        table_data = []
        for row in table.rows:
            if len(row) == len(table.headers):
                row_dict = dict(zip(table.headers, row))
                table_data.append(row_dict)
            else:
                table_data.append({"values": row})

        key = table.table_type
        if key in result["data"]:
            key = f"{key}_p{table.page_num}"
        result["data"][key] = {
            "headers": table.headers,
            "rows": table_data,
            "page": table.page_num,
        }

    return result
