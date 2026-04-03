"""
Level 3 — Agentic Web RAG using Tavily.
Runs 5 intelligence queries (promoter bg, eCourts, RBI, sector, news)
and indexes results into govt/external ChromaDB collections.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List
from dataclasses import dataclass

try:
    from tavily import TavilyClient
except ImportError:  # pragma: no cover - optional dependency
    TavilyClient = None

from llama_index.core import Document

from .indexer import DocumentIndexer
from ..services.llm_client import llm


@dataclass
class WebIntelReport:
    queries_run: List[str]
    results_indexed: int
    key_findings: List[str]
    litigation_found: bool
    adverse_media: bool
    rbi_watchlist_hit: bool
    status: str = "completed"
    skipped_reason: str | None = None
    query_reports: List[dict] | None = None


LITIGATION_KEYWORDS = ["drt", "nclt", "insolvency", "court case", "default", "npa",
                        "debt recovery", "winding up", "injunction", "arrest"]
ADVERSE_KEYWORDS    = ["fraud", "scam", "raid", "arrested", "seized", "fir", "cheating"]
RBI_KEYWORDS        = ["wilful defaulter", "rbi list", "watchlist", "npa declared"]


class WebRAGAgent:
    def __init__(
        self,
        govt_indexer: DocumentIndexer,
        external_indexer: DocumentIndexer,
        company_name: str,
        promoter_name: str,
        industry: str
    ):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.tavily = TavilyClient(api_key=self.api_key) if TavilyClient is not None and self.api_key else None
        self.govt = govt_indexer
        self.external = external_indexer
        self.company = company_name
        self.promoter = promoter_name
        self.industry = industry

    def _fetch_and_index(
        self,
        query: str,
        indexer: DocumentIndexer,
        trust_level: float,
        query_type: str
    ) -> tuple[List[str], List[str]]:
        if self.tavily is None:
            return [], []
        results = self.tavily.search(query=query, max_results=5)
        indexed_texts = []
        source_urls = []

        for r in results.get("results", []):
            content = r.get("content", "")
            source_url = r.get("url", "")
            if source_url:
                source_urls.append(source_url)
            paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > 80]

            for para in paragraphs:
                doc = Document(
                    text=para,
                    metadata={
                        "doc_type": "web_article",
                        "query_type": query_type,
                        "source_url": r.get("url", ""),
                        "source_title": r.get("title", ""),
                        "trust_level": trust_level,
                        "retrieved_at": datetime.now().isoformat(),
                        "company": self.company,
                    }
                )
                indexer.add_documents(
                    [doc],
                    document_id=f"{query_type}:{source_url or 'unknown'}",
                    source_kind="web_intelligence",
                    source_label=r.get("title", query_type),
                    doc_type="web_article",
                    source_path=source_url or None,
                )
                indexed_texts.append(para)

        return indexed_texts, source_urls

    def _synthesize_finding(self, texts: List[str], context: str) -> str:
        if not texts:
            return f"No material findings for: {context}"

        combined = "\n\n".join(texts[:3])
        prompt = f"""Summarize the key credit-relevant finding from these search results about {self.company}.
Context: {context}

Results:
{combined}

Respond in ONE sentence, starting with the company name. Focus on facts relevant to credit risk."""

        return llm.generate_sync(prompt, max_tokens=200)

    def _check_keywords(self, texts: List[str], keywords: List[str]) -> bool:
        combined = " ".join(texts).lower()
        return any(kw in combined for kw in keywords)

    def run(self) -> WebIntelReport:
        if self.tavily is None:
            return WebIntelReport(
                queries_run=[],
                results_indexed=0,
                key_findings=["Web intelligence skipped because Tavily is not configured in this runtime."],
                litigation_found=False,
                adverse_media=False,
                rbi_watchlist_hit=False,
                status="skipped",
                skipped_reason="tavily_unavailable",
                query_reports=[],
            )

        queries = [
            (f"{self.company} {self.promoter} fraud default case India",
             self.external, 0.6, "promoter_background"),
            (f"{self.company} DRT NCLT insolvency court case India",
             self.govt, 0.9, "litigation"),
            (f"{self.company} {self.promoter} RBI wilful defaulter NPA",
             self.govt, 0.9, "rbi_watchlist"),
            (f"{self.industry} sector RBI regulation headwind India 2024",
             self.external, 0.6, "sector_intelligence"),
            (f"{self.company} news 2024 financial operational",
             self.external, 0.6, "recent_news"),
        ]

        all_texts  = []
        findings   = []
        total_docs = 0
        query_reports = []

        for query, indexer, trust, qtype in queries:
            retrieved_at = datetime.now().isoformat()
            try:
                texts, source_urls = self._fetch_and_index(query, indexer, trust, qtype)
                all_texts.extend(texts)
                total_docs += len(texts)
                finding = self._synthesize_finding(texts, qtype)
                findings.append(finding)
                query_reports.append(
                    {
                        "query": query,
                        "query_type": qtype,
                        "status": "completed" if texts else "empty",
                        "results_indexed": len(texts),
                        "source_urls": source_urls[:5],
                        "retrieved_at": retrieved_at,
                        "target_collection": "government_authoritative" if indexer is self.govt else "external_unverified",
                        "key_finding": finding,
                    }
                )
            except Exception as exc:
                query_reports.append(
                    {
                        "query": query,
                        "query_type": qtype,
                        "status": "failed",
                        "results_indexed": 0,
                        "source_urls": [],
                        "retrieved_at": retrieved_at,
                        "target_collection": "government_authoritative" if indexer is self.govt else "external_unverified",
                        "key_finding": f"Query failed: {exc}",
                    }
                )

        return WebIntelReport(
            queries_run=[q[0] for q in queries],
            results_indexed=total_docs,
            key_findings=findings,
            litigation_found=self._check_keywords(all_texts, LITIGATION_KEYWORDS),
            adverse_media=self._check_keywords(all_texts, ADVERSE_KEYWORDS),
            rbi_watchlist_hit=self._check_keywords(all_texts, RBI_KEYWORDS),
            status="completed",
            skipped_reason=None,
            query_reports=query_reports,
        )
