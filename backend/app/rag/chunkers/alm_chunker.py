from __future__ import annotations

from .common import build_documents, split_text, stringify_payload


class ALMChunker:
    def __init__(self, company_name: str):
        self.company_name = company_name

    def chunk(self, alm_report):
        text = f"Company: {self.company_name}\nALM report:\n{stringify_payload(alm_report)}"
        return build_documents(
            split_text(text),
            {"source": f"{self.company_name} ALM", "doc_type": "ALM"},
        )
