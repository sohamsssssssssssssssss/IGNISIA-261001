from __future__ import annotations

from .common import build_documents, split_text, stringify_payload


class PortfolioChunker:
    def __init__(self, company_name: str):
        self.company_name = company_name

    def chunk(self, portfolio_report):
        text = (
            f"Company: {self.company_name}\n"
            f"Portfolio cuts:\n{stringify_payload(portfolio_report)}"
        )
        return build_documents(
            split_text(text),
            {"source": f"{self.company_name} portfolio cuts", "doc_type": "PORTFOLIO_CUTS"},
        )
