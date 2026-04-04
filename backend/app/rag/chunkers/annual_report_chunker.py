from __future__ import annotations

from .common import build_documents, read_text_file, split_text


class AnnualReportChunker:
    def __init__(self, fiscal_year: str):
        self.fiscal_year = fiscal_year

    def chunk_pdf(self, pdf_path: str):
        text = read_text_file(pdf_path)
        return build_documents(
            split_text(text),
            {"source": f"Annual report {self.fiscal_year}", "doc_type": "ANNUAL_REPORT"},
        )
