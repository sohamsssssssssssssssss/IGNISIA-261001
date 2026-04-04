from __future__ import annotations

from .common import build_documents, split_text, stringify_payload


class BorrowingChunker:
    def __init__(self, company_name: str):
        self.company_name = company_name

    def chunk(self, borrowing_profile):
        text = (
            f"Company: {self.company_name}\n"
            f"Borrowing profile:\n{stringify_payload(borrowing_profile)}"
        )
        return build_documents(
            split_text(text),
            {"source": f"{self.company_name} borrowing profile", "doc_type": "BORROWING_PROFILE"},
        )
