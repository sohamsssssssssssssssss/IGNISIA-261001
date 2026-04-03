# Intelli-Credit Pitch Deck

## Slide 1 — The Problem
**The Data Paradox in Indian Corporate Lending**
- Indian banks have access to unparalleled digital infrastructure (GSTN, MCA, EPFO, eCourts).
- Yet, analyzing a single mid-market corporate borrower still takes **2–3 weeks of analyst time**.
- Why? The data is fragmented across JSONs, XMLs, Scanned PDFs, and unstructured web portals.
- 50% of an analyst's time is spent compiling data, leaving less time for actual risk judgment.

## Slide 2 — The Solution
**Intelli-Credit: The AI Analyst that reads everything and forgets nothing.**
An AI-powered Corporate Credit Appraisal Engine built specifically for the Indian lending ecosystem, compressing a 3-week CAM generation process into under 1 hour.
**The Three Pillars:**
1. **Data Ingestor:** Custom parsers for GSTR, ITR-6, 26AS, and Bank Statements.
2. **Research Agents:** Contextual web scraping (MCA, eCourts, News) mapped against 20+ risk vectors.
3. **CBM Recommendation Engine:** Interpretable neural scoring that spits out a ready-to-sign Credit Appraisal Memo.

## Slide 3 — Architecture
[Insert System Architecture Diagram Here]
- **Ingestion:** PaddleOCR + Python Pydantic Models -> Delta Lake
- **Agents:** Orchestrator (LinUCB) -> Playwright/Tavily Agents (MCA, eCourts, News)
- **Engine:** PyTorch Concept Bottleneck Model -> SHAP Explainer -> Word Doc / PDF Gen

## Slide 4 — The India-Specific Advantage
Generic LLMs cannot underwrite an Indian SME. We built localized deterministic checks:
- **GSTR 2A vs 3B Reconciliation:** Flags circular trading risks and fake invoicing instantly.
- **Form 26AS Mismatch Detection:** Correlates TDS payments against declared Schedule BP income.
- **NACH Return Detection:** Parses bank statements specifically for mandate bounces (the earliest delinquency signal).
- **MCA Director Webs:** NetworkX graph traversal to spot promoters connected to 10+ shell entities.
- **eCourts NER:** Scrapes the national portal for active DRT/NCLT litigation flags.

## Slide 5 — Explainability (Why not just GPT-4?)
**The AI Explains. The Human Decides.**
- Black box LLMs hallucinate numbers and fail regulatory audits.
- Our **Concept Bottleneck Model (CBM)** breaks down the borrower into **22 interpretable concepts** across the Five C's of Credit (Character, Capacity, Capital, Collateral, Conditions).
- We use **SHAP** to trace the exact numerical contribution of every feature to the final score.
- Fully compliant: Automatically generates an **RBI Fair Practices Code-compliant Adverse Action Notice** on rejection.

## Slide 6 — Results & Demo Arc
- **Time to CAM:** < 1 Hour.
- **Demo Arc 1 (Arjun Textiles):** Detected a 25% 26AS mismatch, 18% GSTR variance (Circular Trading), and 3 NACH bounces. Final Score: 52/100 (Rejected with Adverse Action Notice).
- **Demo Arc 2 (Clean Borrower):** Strong DSCR, zero litigation, high MSME-adjusted capacity. Final Score: 88/100 (Approved with INR 5Cr Limit).
