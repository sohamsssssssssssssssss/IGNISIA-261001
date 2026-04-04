from __future__ import annotations

from .common import build_documents, split_text, stringify_payload


class ShareholdingChunker:
    def __init__(self, company_name: str):
        self.company_name = company_name

    def chunk(self, shareholding_report):
        text = (
            f"Company: {self.company_name}\n"
            f"Shareholding pattern:\n{stringify_payload(shareholding_report)}"
        )
        return build_documents(
            split_text(text),
            {"source": f"{self.company_name} shareholding", "doc_type": "SHAREHOLDING_PATTERN"},
        )
