from __future__ import annotations

from .common import build_documents, split_text, stringify_payload


class GSTRChunker:
    def __init__(self, gstin: str):
        self.gstin = gstin

    def chunk(self, gstr3b: dict, gstr2a: dict):
        combined = (
            f"GSTIN: {self.gstin}\n"
            f"GSTR-3B:\n{stringify_payload(gstr3b)}\n\n"
            f"GSTR-2A:\n{stringify_payload(gstr2a)}"
        )
        return build_documents(
            split_text(combined),
            {"source": f"{self.gstin} GST returns", "doc_type": "GSTR"},
        )
