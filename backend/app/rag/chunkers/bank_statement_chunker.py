from __future__ import annotations

from .common import build_documents, read_text_file, split_text


class BankStatementChunker:
    def __init__(self, company_name: str):
        self.company_name = company_name

    def chunk_csv(self, csv_path: str):
        text = read_text_file(csv_path)
        return build_documents(
            split_text(text),
            {"source": f"{self.company_name} bank statement", "doc_type": "BANK_STATEMENT"},
        )
