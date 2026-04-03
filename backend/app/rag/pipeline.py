"""
Master RAG Pipeline Orchestrator.
Runs all three levels in sequence and generates Five C's CAM sections.
"""

from dataclasses import dataclass
from typing import Optional
from . import collections as col
from .indexer import DocumentIndexer
from .chunkers.gstr_chunker import GSTRChunker
from .chunkers.annual_report_chunker import AnnualReportChunker
from .chunkers.bank_statement_chunker import BankStatementChunker
from .chunkers.alm_chunker import ALMChunker
from .chunkers.shareholding_chunker import ShareholdingChunker
from .chunkers.borrowing_chunker import BorrowingChunker
from .chunkers.portfolio_chunker import PortfolioChunker
from .contradiction_detector import ContradictionDetector, ContradictionReport
from .web_rag import WebRAGAgent, WebIntelReport
from .query_engine import TrustWeightedQueryEngine, RAGResponse


@dataclass
class RAGPipelineResult:
    chunks_indexed: int
    contradiction_report: ContradictionReport
    web_intel_report: WebIntelReport
    cam_sections: dict  # keyed by Five C
    provenance_summary: dict


class RAGPipeline:
    def __init__(
        self,
        company_name: str,
        promoter_name: str,
        industry: str,
        gstin: str,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
    ):
        self.company = company_name
        self.promoter = promoter_name
        self.industry = industry
        self.gstin = gstin
        self.session_id = session_id
        self.run_id = run_id

        self.borrower_idx  = DocumentIndexer(col.BORROWER_COLLECTION)
        self.govt_idx      = DocumentIndexer(col.GOVT_COLLECTION)
        self.external_idx  = DocumentIndexer(col.EXTERNAL_COLLECTION)

        self.query_engine = TrustWeightedQueryEngine(
            self.borrower_idx, self.govt_idx, self.external_idx
        )

    def _ingest_documents(
        self,
        docs,
        *,
        source_kind: str,
        source_label: str,
        doc_type: str,
        source_path: str | None = None,
    ) -> int:
        return self.borrower_idx.add_documents(
            docs,
            session_id=self.session_id,
            run_id=self.run_id,
            document_id=source_label,
            source_kind=source_kind,
            source_label=source_label,
            doc_type=doc_type,
            source_path=source_path,
            ingestion_version=self.run_id or "v1",
        )

    # ── LEVEL 1 ──────────────────────────────────────────────────────
    def ingest_gstr(self, gstr3b: dict, gstr2a: dict):
        chunker = GSTRChunker(self.gstin)
        docs = chunker.chunk(gstr3b, gstr2a)
        return self._ingest_documents(
            docs,
            source_kind="borrower_submission",
            source_label=f"{self.gstin}-gstr",
            doc_type="GSTR",
        )

    def ingest_annual_report(self, pdf_path: str, fiscal_year: str = "FY24"):
        chunker = AnnualReportChunker(fiscal_year)
        docs = chunker.chunk_pdf(pdf_path)
        return self._ingest_documents(
            docs,
            source_kind="uploaded_document",
            source_label=f"{self.company}-annual-report-{fiscal_year}",
            doc_type="ANNUAL_REPORT",
            source_path=pdf_path,
        )

    def ingest_bank_statement(self, csv_path: str):
        chunker = BankStatementChunker(self.company)
        docs = chunker.chunk_csv(csv_path)
        return self._ingest_documents(
            docs,
            source_kind="uploaded_document",
            source_label=f"{self.company}-bank-statement",
            doc_type="BANK_STATEMENT",
            source_path=csv_path,
        )

    def ingest_alm(self, alm_report):
        """Ingest parsed ALM report into ChromaDB."""
        chunker = ALMChunker(self.company)
        docs = chunker.chunk(alm_report)
        return self._ingest_documents(
            docs,
            source_kind="uploaded_document",
            source_label=f"{self.company}-alm",
            doc_type="ALM",
        )

    def ingest_shareholding(self, shareholding_report):
        """Ingest parsed shareholding pattern into ChromaDB."""
        chunker = ShareholdingChunker(self.company)
        docs = chunker.chunk(shareholding_report)
        return self._ingest_documents(
            docs,
            source_kind="uploaded_document",
            source_label=f"{self.company}-shareholding",
            doc_type="SHAREHOLDING_PATTERN",
        )

    def ingest_borrowing_profile(self, borrowing_profile):
        """Ingest parsed borrowing profile into ChromaDB."""
        chunker = BorrowingChunker(self.company)
        docs = chunker.chunk(borrowing_profile)
        return self._ingest_documents(
            docs,
            source_kind="uploaded_document",
            source_label=f"{self.company}-borrowing-profile",
            doc_type="BORROWING_PROFILE",
        )

    def ingest_portfolio(self, portfolio_report):
        """Ingest parsed portfolio performance data into ChromaDB."""
        chunker = PortfolioChunker(self.company)
        docs = chunker.chunk(portfolio_report)
        return self._ingest_documents(
            docs,
            source_kind="uploaded_document",
            source_label=f"{self.company}-portfolio-cuts",
            doc_type="PORTFOLIO_CUTS",
        )

    # ── LEVEL 2 ──────────────────────────────────────────────────────
    def run_contradiction_detection(self) -> ContradictionReport:
        detector = ContradictionDetector(
            self.borrower_idx, self.govt_idx, self.external_idx
        )
        return detector.detect()

    # ── LEVEL 3 ──────────────────────────────────────────────────────
    def run_web_intelligence(self) -> WebIntelReport:
        agent = WebRAGAgent(
            self.govt_idx, self.external_idx,
            self.company, self.promoter, self.industry
        )
        return agent.run()

    # ── SYNTHESIS ─────────────────────────────────────────────────────
    def generate_cam_sections(self) -> dict:
        queries = {
            "character": (
                f"What is the character and integrity of {self.company} promoters? "
                f"Include litigation, defaults, adverse history, shareholding pledge status, and promoter track record."
            ),
            "capacity": (
                f"What is {self.company}'s debt service capacity? Include DSCR, cash flows, "
                f"repayment ability, ALM maturity gaps, and collection efficiency from portfolio data."
            ),
            "capital": (
                f"What is {self.company}'s capital structure? Net worth, debt-to-equity, "
                f"financial leverage, borrowing profile utilization, and existing lender exposure."
            ),
            "collateral": (
                f"What collateral or security has {self.company} offered? LTV and coverage ratios. "
                f"Include portfolio quality, NPA%, and provision coverage as secondary security indicators."
            ),
            "conditions": (
                f"What are the macroeconomic and sector conditions affecting {self.company} in {self.industry}? "
                f"Include sector trends, sub-sector outlook, and macro indicators."
            ),
        }
        return {k: self.query_engine.query(v) for k, v in queries.items()}

    # ── FULL PIPELINE ─────────────────────────────────────────────────
    def run_full(
        self,
        gstr3b: dict = None,
        gstr2a: dict = None,
        annual_report_path: str = None,
        bank_statement_path: str = None,
        alm_report=None,
        shareholding_report=None,
        borrowing_profile=None,
        portfolio_report=None,
    ) -> RAGPipelineResult:
        n1 = self.ingest_gstr(gstr3b, gstr2a) if gstr3b and gstr2a else 0
        n2 = self.ingest_annual_report(annual_report_path) if annual_report_path else 0
        n3 = self.ingest_bank_statement(bank_statement_path) if bank_statement_path else 0

        n4 = self.ingest_alm(alm_report) if alm_report else 0
        n5 = self.ingest_shareholding(shareholding_report) if shareholding_report else 0
        n6 = self.ingest_borrowing_profile(borrowing_profile) if borrowing_profile else 0
        n7 = self.ingest_portfolio(portfolio_report) if portfolio_report else 0
        provenance_summary = {
            "session_id": self.session_id,
            "pipeline_run_id": self.run_id,
            "documents": [
                {"document_id": f"{self.gstin}-gstr", "doc_type": "GSTR", "chunks_indexed": n1},
                {"document_id": f"{self.company}-annual-report-FY24", "doc_type": "ANNUAL_REPORT", "chunks_indexed": n2},
                {"document_id": f"{self.company}-bank-statement", "doc_type": "BANK_STATEMENT", "chunks_indexed": n3},
                {"document_id": f"{self.company}-alm", "doc_type": "ALM", "chunks_indexed": n4},
                {"document_id": f"{self.company}-shareholding", "doc_type": "SHAREHOLDING_PATTERN", "chunks_indexed": n5},
                {"document_id": f"{self.company}-borrowing-profile", "doc_type": "BORROWING_PROFILE", "chunks_indexed": n6},
                {"document_id": f"{self.company}-portfolio-cuts", "doc_type": "PORTFOLIO_CUTS", "chunks_indexed": n7},
            ],
        }
        provenance_summary["documents"] = [
            item for item in provenance_summary["documents"] if item["chunks_indexed"] > 0
        ]

        contradiction_report = self.run_contradiction_detection()
        web_intel_report     = self.run_web_intelligence()
        cam_sections         = self.generate_cam_sections()

        return RAGPipelineResult(
            chunks_indexed=n1 + n2 + n3 + n4 + n5 + n6 + n7,
            contradiction_report=contradiction_report,
            web_intel_report=web_intel_report,
            cam_sections=cam_sections,
            provenance_summary=provenance_summary,
        )
