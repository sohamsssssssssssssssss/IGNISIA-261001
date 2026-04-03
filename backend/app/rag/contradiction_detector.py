"""
Level 2 — Cross-Document Contradiction Detector.
Runs revenue reconciliation (numeric) and integrity checks (semantic via Ollama).
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass
from typing import List, Optional

try:
    import ollama
except ImportError:  # pragma: no cover - optional dependency
    ollama = None

from .indexer import DocumentIndexer


@dataclass
class ContradictionResult:
    query: str
    source_a: str
    value_a: str
    source_b: str
    value_b: str
    variance_pct: Optional[float]
    severity: str  # "LOW" | "MEDIUM" | "HIGH"
    explanation: str


@dataclass
class ContradictionReport:
    contradictions: List[ContradictionResult]
    overall_risk: str
    primary_driver: str


REVENUE_QUERIES = [
    "total annual revenue turnover declared",
    "taxable turnover GST filing",
    "total bank credit inflows annual",
]

INTEGRITY_QUERIES = [
    "outstanding debt borrowings loan",
    "contingent liabilities legal disputes",
    "director promoter court case litigation default",
]


def _extract_inr_value(text: str) -> Optional[float]:
    patterns = [
        r'₹\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
        r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
        r'INR\s*([\d,]+(?:\.\d+)?)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


class ContradictionDetector:
    def __init__(
        self,
        borrower_indexer: DocumentIndexer,
        govt_indexer: DocumentIndexer,
        external_indexer: DocumentIndexer
    ):
        self.borrower = borrower_indexer
        self.govt = govt_indexer
        self.external = external_indexer

    def _cross_query(self, query: str, top_k: int = 3) -> dict:
        return {
            "borrower": self.borrower.query(query, top_k=top_k),
            "govt":     self.govt.query(query, top_k=top_k),
            "external": self.external.query(query, top_k=top_k),
        }

    def _check_numeric_contradiction(self, query: str) -> Optional[ContradictionResult]:
        results = self._cross_query(query)
        values = {}
        for source, nodes in results.items():
            for node in nodes:
                val = _extract_inr_value(node["text"])
                if val:
                    values[source] = (val, node["metadata"].get("source", source))
                    break

        sources = list(values.keys())
        if len(sources) < 2:
            return None

        s_a, s_b = sources[0], sources[1]
        v_a, v_b = values[s_a][0], values[s_b][0]
        variance = abs(v_a - v_b) / max(v_a, v_b) * 100 if max(v_a, v_b) > 0 else 0

        if variance < 15:
            return None

        severity = "HIGH" if variance > 40 else "MEDIUM" if variance > 20 else "LOW"
        return ContradictionResult(
            query=query,
            source_a=values[s_a][1],
            value_a=f"₹{v_a:.1f} Cr",
            source_b=values[s_b][1],
            value_b=f"₹{v_b:.1f} Cr",
            variance_pct=round(variance, 1),
            severity=severity,
            explanation=f"{variance:.1f}% gap between {s_a} and {s_b} sources"
        )

    def _check_semantic_contradiction(self, query: str) -> List[ContradictionResult]:
        results = self._cross_query(query)
        all_chunks = []
        for source, nodes in results.items():
            for n in nodes:
                all_chunks.append(f"[{source.upper()} — {n['metadata'].get('source','')}]:\n{n['text']}")

        if len(all_chunks) < 2:
            return []
        if ollama is None:
            return []

        prompt = f"""You are a credit risk analyst. Review these excerpts from different sources about the same borrower.

QUERY: {query}

SOURCES:
{chr(10).join(all_chunks)}

Identify any contradictions between sources. For each contradiction found, respond ONLY with valid JSON array:
[
  {{
    "source_a": "source name",
    "value_a": "what source A says",
    "source_b": "source name",
    "value_b": "what source B says",
    "severity": "HIGH|MEDIUM|LOW",
    "explanation": "one sentence explanation"
  }}
]

If no contradictions, return: []
"""
        try:
            resp = ollama.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": prompt}]
            )
            raw = resp["message"]["content"].strip()
        except Exception:
            return []
        try:
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match is None:
                return []
            data = json.loads(match.group())
            return [
                ContradictionResult(
                    query=query,
                    source_a=d["source_a"], value_a=d["value_a"],
                    source_b=d["source_b"], value_b=d["value_b"],
                    variance_pct=None,
                    severity=d["severity"],
                    explanation=d["explanation"]
                ) for d in data
            ]
        except Exception:
            return []

    def detect(self) -> ContradictionReport:
        contradictions = []

        for q in REVENUE_QUERIES:
            result = self._check_numeric_contradiction(q)
            if result:
                contradictions.append(result)

        for q in INTEGRITY_QUERIES:
            results = self._check_semantic_contradiction(q)
            contradictions.extend(results)

        high = [c for c in contradictions if c.severity == "HIGH"]
        med  = [c for c in contradictions if c.severity == "MEDIUM"]

        overall_risk = "HIGH" if high else "MEDIUM" if med else "LOW"
        primary_driver = (
            contradictions[0].explanation if contradictions
            else "No material contradictions detected"
        )

        return ContradictionReport(
            contradictions=contradictions,
            overall_risk=overall_risk,
            primary_driver=primary_driver
        )
