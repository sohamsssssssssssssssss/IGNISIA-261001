import React, { useState, useEffect, useRef, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';

function buildApiHeaders(extra = {}) {
    return {
        ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
        ...extra,
    };
}

function withAuthQuery(url) {
    if (!API_TOKEN) return url;
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}token=${encodeURIComponent(API_TOKEN)}`;
}

/* ─────────────────────── DATA ─────────────────────── */
const SCENARIOS = {
    reject: {
        company: 'Arjun Textiles Pvt. Ltd.',
        cin: 'U17111MH2019PTC012345',
        sector: 'Textiles — Spinning & Weaving',
        vintage: '5 years',
        promoter: 'Arjun Singhania',
        pan: 'AABCA1234Z',
        turnover: '₹18.2 Cr (FY24)',
        cibil: 'CMR-6 (Below Average)',
        score: 52,
        verdict: 'REJECT',
        limit: null,
        rate: null,
        rationale: 'The applicant presents an unacceptable risk profile characterised by a material three-way revenue discrepancy — GST filings report ₹12 Cr, bank credits total ₹4 Cr, while the Annual Report claims ₹18 Cr. This irreconcilable variance, combined with active DRT litigation of ₹45L (eCourts reference DRT/MUM/2024/1847), director linkages to two entities classified as NPA by RBI, and a CIBIL CMR-6 rating, places the borrower firmly below the institution\'s risk appetite threshold.',
        fiveCs: { Character: 0.35, Capacity: 0.40, Capital: 0.55, Collateral: 0.30, Conditions: 0.45 },
        loan: { type: 'Working Capital', amount: '₹3.00 Cr', tenure: '12 months', rate: '14.2%' },
        shap: [
            { feature: 'Revenue Mismatch (3-way)', value: -0.18, color: '#C8293A' },
            { feature: 'DRT Litigation Active', value: -0.14, color: '#C8293A' },
            { feature: 'CIBIL CMR-6', value: -0.11, color: '#C8293A' },
            { feature: 'Shell Entity Linkage', value: -0.09, color: '#C97C14' },
            { feature: 'GSTR 2A/3B Variance', value: -0.07, color: '#C97C14' },
            { feature: 'Cash Deposit Spikes', value: -0.05, color: '#C97C14' },
            { feature: 'Sector Growth (Textiles)', value: 0.03, color: '#25A05E' },
            { feature: 'Collateral Coverage', value: 0.02, color: '#25A05E' },
        ],
        pipeline: [
            { t: 400, sev: 'INFO', msg: '[L1-RAG] Chunking GSTR at invoice-level (not token windows)…' },
            { t: 800, sev: 'OK', msg: '[L1-RAG] 47 chunks indexed → borrower_provided collection' },
            { t: 1200, sev: 'INFO', msg: '[L1-RAG] Annual Report — section-aware chunking (8 sections detected)' },
            { t: 1600, sev: 'INFO', msg: '[L1-RAG] Bank statement — 24 monthly window chunks indexed' },
            { t: 1800, sev: 'INFO', msg: '[L1-RAG] ALM — 9 maturity bucket chunks indexed (2 negative gaps)' },
            { t: 2000, sev: 'WARN', msg: '[L1-RAG] Shareholding — promoter pledge 42% flagged (>30% threshold)' },
            { t: 2200, sev: 'INFO', msg: '[L1-RAG] Borrowing Profile — 3 lenders, ₹8.2Cr outstanding, 1 NPA facility' },
            { t: 2400, sev: 'WARN', msg: '[L1-RAG] Portfolio Cuts — Gross NPA 6.8%, collection efficiency 82%' },
            { t: 2800, sev: 'CRIT', msg: '[L2-RAG] ⚠ Revenue gap — GST ₹12.07Cr vs Bank ₹4.01Cr vs AR ₹18.2Cr (67%)' },
            { t: 3200, sev: 'WARN', msg: '[L2-RAG] 26AS TDS ₹3.2L vs ITR Gross ₹4.1L — 22% ITC delta flagged' },
            { t: 3600, sev: 'INFO', msg: '[L3-RAG] Sector Research — Textiles: 3% YoY, cotton +12%, NEUTRAL outlook' },
            { t: 4000, sev: 'CRIT', msg: '[L3-RAG] ⚠ DRT case found — indexed to govt_authoritative collection' },
            { t: 4400, sev: 'WARN', msg: '[L3-RAG] MCA director Arjun Singhania → 4 entities (2 NPA-linked)' },
            { t: 4800, sev: 'INFO', msg: '[TRI] Triangulation: 3 contradictions, 1 aligned, 1 unverified' },
            { t: 5200, sev: 'INFO', msg: '[SYN] Trust-weighted merge — 3 collections → re-ranked by weighted score' },
            { t: 5600, sev: 'INFO', msg: '[SYN] Generating SWOT analysis via grounded Llama 3.2…' },
            { t: 6000, sev: 'INFO', msg: '[CBM] SHAP attribution computed — 22 concept nodes scored' },
            { t: 6400, sev: 'CRIT', msg: '[VERDICT] Score 52.0/100 — RECOMMENDATION: REJECT' },
        ],
        contradictions: [
            { source1: 'GST Filings', val1: '₹12.07 Cr', source2: 'Bank Credits', val2: '₹4.01 Cr', source3: 'Annual Report', val3: '₹18.2 Cr', gap: '67%' },
        ],
        riskFlags: [
            { sev: 'CRIT', source: 'GST / BANK / AR', text: 'Revenue mismatch across 3 pillars — 67% gap detected' },
            { sev: 'CRIT', source: 'ECOURTS', text: 'Active DRT litigation — ₹45L disputed (DRT/MUM/2024/1847)' },
            { sev: 'WARN', source: 'MCA', text: 'Director linked to 2 NPA-classified entities' },
            { sev: 'WARN', source: 'CIBIL', text: 'CMR-6 score — below institutional risk threshold' },
        ],
        devil: 'The officer rated Management Quality at 4/5, however eCourts data reveals an active DRT case (₹45L disputed) and MCA records show the director is linked to two NPA-classified shell entities. This contradicts a "high quality" management assessment. Recommend reducing Management Quality to 2/5, which would decrease the overall score by approximately 6 points.',
        swot: {
            strengths: [
                'Established presence in textile spinning & weaving segment (5-year vintage)',
                'Factory infrastructure with existing production capacity',
            ],
            weaknesses: [
                'Severe 3-way revenue mismatch: GST ₹12Cr vs Bank ₹4Cr vs AR ₹18Cr (67% gap)',
                'Active DRT litigation of ₹45L with ongoing proceedings',
                'CIBIL CMR-6 — below institutional risk appetite threshold',
                'Director linked to 2 NPA-classified shell entities',
                'GSTR 2A/3B ITC variance of 18% — circular trading indicator',
            ],
            opportunities: [
                'Textile sector showing 3% YoY growth nationally',
                'Government PLI scheme for technical textiles',
            ],
            threats: [
                'Negative press: labour dispute (Feb 2025)',
                'Rising cotton prices (up 12% YoY)',
                'Shell entity linkages expose promoter to ED/SFIO risk',
                'RBI increased risk weight on unsecured commercial loans to 150%',
            ],
        },
        classification: [
            { filename: 'ArjunTextiles_GSTR3B_FY24.json', predicted: 'ANNUAL_REPORT', confidence: 0.45, evidence: 'Low confidence — content scan ambiguous', corrected: 'GSTR_FILINGS', status: 'EDITED' },
            { filename: 'ArjunTextiles_AnnualReport_FY24.pdf', predicted: 'ANNUAL_REPORT', confidence: 0.92, evidence: 'Filename + content match', corrected: null, status: 'APPROVED' },
            { filename: 'ArjunTextiles_BankStmt_SBI.csv', predicted: 'BORROWING_PROFILE', confidence: 0.55, evidence: 'Content scan: "outstanding", "lender"', corrected: 'BANK_STATEMENT', status: 'EDITED' },
            { filename: 'ArjunTextiles_ALM_Q3FY24.xlsx', predicted: 'ALM', confidence: 0.88, evidence: 'Filename matches pattern for ALM', corrected: null, status: 'APPROVED' },
            { filename: 'ArjunTextiles_Shareholding_SEBI.csv', predicted: 'SHAREHOLDING_PATTERN', confidence: 0.85, evidence: 'Filename matches pattern', corrected: null, status: 'APPROVED' },
        ],
        triangulation: [
            { external: 'eCourts: Active DRT case — ₹45L disputed', internal: 'AR: No contingent liabilities disclosed', alignment: 'CONTRADICTED', sev: 'CRIT', rec: 'AR likely omits material litigation. Flag under IndAS 37.' },
            { external: 'MCA: Director linked to 2 NPA entities', internal: 'Shareholding: No related-party disclosure', alignment: 'CONTRADICTED', sev: 'CRIT', rec: 'Request full related-party transaction schedule.' },
            { external: 'News: Labour dispute (Feb 2025)', internal: 'Bank: Salary credits declined 30%', alignment: 'ALIGNED', sev: 'WARN', rec: 'Labour dispute corroborated by bank data.' },
            { external: 'Sector NPA: 8.2% (RBI Q3)', internal: 'Portfolio: Gross NPA 6.8%', alignment: 'CONTRADICTED', sev: 'WARN', rec: 'Risk worse than sector average.' },
            { external: 'Cotton prices +12% YoY', internal: 'No hedging visible in bank txns', alignment: 'UNVERIFIED', sev: 'INFO', rec: 'Request commodity hedging policy.' },
        ],
        schemaMappings: [
            { docType: 'ANNUAL_REPORT', rawField: 'Revenue from Operations', mappedTo: 'revenue', value: '₹18.2 Cr', confidence: 0.95 },
            { docType: 'ANNUAL_REPORT', rawField: 'Total Borrowings (Note 14)', mappedTo: 'total_debt', value: '₹8.2 Cr', confidence: 0.90 },
            { docType: 'ALM', rawField: '1-7 days Outflows', mappedTo: 'total_liabilities', value: '₹2.1 Cr', confidence: 0.88 },
            { docType: 'SHAREHOLDING_PATTERN', rawField: 'Promoter & Promoter Group', mappedTo: 'promoter_holding', value: '72%', confidence: 0.97 },
            { docType: 'BORROWING_PROFILE', rawField: 'SBI Term Loan O/S', mappedTo: 'outstanding', value: '₹4.5 Cr', confidence: 0.92 },
            { docType: 'PORTFOLIO_CUTS', rawField: '6-12M Bucket GNPA', mappedTo: 'gross_npa_pct', value: '6.8%', confidence: 0.85 },
        ],
        sectorResearch: {
            outlook: 'NEUTRAL', growth: '3% YoY',
            sub: 'Spinning sub-sector faces margin pressure from rising cotton prices. PLI adoption slow.',
            macro: ['Cotton: ₹62,500/candy (+12%)', 'EU orders stable, US -5%', 'INR/USD: ₹83.2'],
            risks: ['Raw material volatility', 'Labour cost pressure', 'Bangladesh/Vietnam competition'],
        },
    },
    approve: {
        company: 'CleanTech Manufacturing Ltd.',
        cin: 'U28100KA2018PTC098765',
        sector: 'Industrial Machinery — CNC & Automation',
        vintage: '7 years',
        promoter: 'Vikram Mehta',
        pan: 'BBMCV5678K',
        turnover: '₹42.5 Cr (FY24)',
        cibil: 'CMR-3 (Low Risk)',
        score: 88.5,
        verdict: 'APPROVE',
        limit: '₹5.00 Cr',
        rate: { base: 8.5, risk: 1.5, sector: -0.5, total: 9.5 },
        rationale: 'CleanTech Manufacturing demonstrates robust financial health across all verification pillars. Revenue figures reconcile within 2% tolerance across GST filings (₹41.8 Cr), bank credits (₹42.1 Cr), and audited financials (₹42.5 Cr). No adverse litigation detected. CIBIL CMR-3 rating confirms strong payment discipline. The CNC machinery sector shows 14% YoY growth nationally, providing favourable macro tailwinds. Recommended for sanction at ₹5.00 Cr with a blended rate of 9.50%.',
        fiveCs: { Character: 0.90, Capacity: 0.85, Capital: 0.88, Collateral: 0.82, Conditions: 0.91 },
        loan: { type: 'Term Loan', amount: '₹5.00 Cr', tenure: '60 months', rate: '9.5%' },
        shap: [
            { feature: 'Revenue Consistency (3-way)', value: 0.15, color: '#25A05E' },
            { feature: 'CIBIL CMR-3', value: 0.12, color: '#25A05E' },
            { feature: 'Sector Growth (CNC)', value: 0.10, color: '#25A05E' },
            { feature: 'Zero Litigation', value: 0.08, color: '#25A05E' },
            { feature: 'Healthy Cash Flow', value: 0.07, color: '#25A05E' },
            { feature: 'Collateral Coverage 1.6x', value: 0.05, color: '#25A05E' },
            { feature: 'Promoter Concentration', value: -0.03, color: '#C97C14' },
            { feature: 'Single-bank Dependency', value: -0.02, color: '#C97C14' },
        ],
        pipeline: [
            { t: 400, sev: 'INFO', msg: '[L1-RAG] Chunking GSTR at invoice-level (not token windows)…' },
            { t: 800, sev: 'OK', msg: '[L1-RAG] 52 chunks indexed → borrower_provided collection' },
            { t: 1200, sev: 'INFO', msg: '[L1-RAG] Annual Report — section-aware chunking (10 sections detected)' },
            { t: 1400, sev: 'OK', msg: '[L1-RAG] ALM — 9 maturity buckets indexed (0 negative gaps)' },
            { t: 1600, sev: 'OK', msg: '[L1-RAG] Shareholding — promoter 67%, pledge 0% ✓' },
            { t: 1800, sev: 'OK', msg: '[L1-RAG] Borrowing Profile — 2 lenders, clean repayment, 0 NPA' },
            { t: 2000, sev: 'OK', msg: '[L1-RAG] Portfolio — Gross NPA 1.2%, collection efficiency 97%' },
            { t: 2400, sev: 'OK', msg: '[L2-RAG] Cross-doc reconciliation — GST ₹41.8Cr ↔ Bank ₹42.1Cr — 0.7% OK' },
            { t: 2800, sev: 'INFO', msg: '[L3-RAG] Sector Research — CNC: 14% YoY, defence orders up, POSITIVE' },
            { t: 3200, sev: 'OK', msg: '[L3-RAG] No litigation found — all clear' },
            { t: 3600, sev: 'OK', msg: '[L3-RAG] MCA director Vikram Mehta — clean record, no linked NPAs' },
            { t: 4000, sev: 'OK', msg: '[L3-RAG] Positive coverage: "CleanTech wins ₹8Cr defence order"' },
            { t: 4400, sev: 'INFO', msg: '[TRI] Triangulation: 4 aligned, 0 contradictions, 1 unverified' },
            { t: 4800, sev: 'INFO', msg: '[SYN] Trust-weighted merge — 3 collections → re-ranked' },
            { t: 5200, sev: 'INFO', msg: '[SYN] Generating SWOT analysis via grounded Llama 3.2…' },
            { t: 5600, sev: 'INFO', msg: '[CBM] SHAP attribution computed — 22 concept nodes scored' },
            { t: 6000, sev: 'OK', msg: '[VERDICT] Score 88.5/100 — RECOMMENDATION: APPROVE' },
        ],
        contradictions: [],
        riskFlags: [
            { sev: 'OK', source: 'GST / BANK', text: 'Revenue reconciled within 2% tolerance' },
            { sev: 'OK', source: 'ECOURTS', text: 'Zero litigation on eCourts / DRT' },
            { sev: 'OK', source: 'MCA', text: 'Clean director history — no linked NPAs' },
            { sev: 'OK', source: 'CIBIL', text: 'CMR-3 rating — strong credit posture' },
        ],
        devil: 'Management quality assessment of 4/5 is supported by clean MCA records, no eCourts DRT cases, and positive press coverage. No contradictions found in the qualitative override. The officer\'s field observations are consistent with quantitative signals.',
        swot: {
            strengths: [
                'Revenue consistency: GST, Bank, AR within 2% tolerance',
                'CIBIL CMR-3 — strong institutional credit discipline',
                'Zero litigation across eCourts/DRT',
                'DSCR 1.8x — well above 1.25x threshold',
                'Collateral SCR 1.6x with SARFAESI enforceability',
                'Promoter equity stake 67% — strong skin-in-the-game',
            ],
            weaknesses: [
                'Single-bank dependency for working capital',
                'Promoter concentration 67% — key-man risk',
            ],
            opportunities: [
                'CNC & Automation sector growing 14% YoY',
                '₹8Cr defence order win — govt contracting pipeline',
                'Make in India incentives for indigenous manufacturing',
            ],
            threats: [
                'Geopolitical supply chain risk on imported CNC parts',
                'Rising interest rate environment',
                'Foreign competitors with lower pricing',
            ],
        },
        classification: [
            { filename: 'CleanTech_AnnualReport_FY24.pdf', predicted: 'ANNUAL_REPORT', confidence: 0.95, evidence: 'Filename + content match', corrected: null, status: 'APPROVED' },
            { filename: 'CleanTech_ALM_Q3FY24.xlsx', predicted: 'ALM', confidence: 0.90, evidence: 'Filename matches ALM pattern', corrected: null, status: 'APPROVED' },
            { filename: 'CleanTech_Shareholding.csv', predicted: 'SHAREHOLDING_PATTERN', confidence: 0.88, evidence: 'Filename match', corrected: null, status: 'APPROVED' },
            { filename: 'CleanTech_Borrowings_FY24.csv', predicted: 'BORROWING_PROFILE', confidence: 0.85, evidence: 'Filename match', corrected: null, status: 'APPROVED' },
            { filename: 'CleanTech_Portfolio_FY24.csv', predicted: 'PORTFOLIO_CUTS', confidence: 0.82, evidence: 'Content scan: "NPA", "collection"', corrected: null, status: 'APPROVED' },
        ],
        triangulation: [
            { external: 'eCourts: Zero litigation for CleanTech or Vikram Mehta', internal: 'AR: "No contingent liabilities" — IndAS 37 compliant', alignment: 'ALIGNED', sev: 'INFO', rec: 'Clean legal record confirmed.' },
            { external: 'News: CleanTech wins ₹8Cr defence order', internal: 'Bank: ₹2.1Cr advance received Feb 2025', alignment: 'ALIGNED', sev: 'INFO', rec: 'Order win corroborated by bank inflow.' },
            { external: 'CNC sector growth 14% YoY (IMTMA)', internal: 'GST revenue growth 11% YoY', alignment: 'ALIGNED', sev: 'INFO', rec: 'Growing slightly below sector but healthy.' },
            { external: 'MCA: Director clean — no NPA entities', internal: 'Shareholding: 67% holding, zero pledge', alignment: 'ALIGNED', sev: 'INFO', rec: 'Strong governance indicators.' },
            { external: 'Semiconductor supply chain disruption (global)', internal: 'Borrowing: no hedging or diversification', alignment: 'UNVERIFIED', sev: 'WARN', rec: 'Discuss supply chain diversification.' },
        ],
        schemaMappings: [
            { docType: 'ANNUAL_REPORT', rawField: 'Revenue from Operations', mappedTo: 'revenue', value: '₹42.5 Cr', confidence: 0.97 },
            { docType: 'ANNUAL_REPORT', rawField: 'Total Equity', mappedTo: 'net_worth', value: '₹18.2 Cr', confidence: 0.95 },
            { docType: 'ALM', rawField: 'Net Cumulative Gap', mappedTo: 'cumulative_gap', value: '₹+4.2 Cr', confidence: 0.90 },
            { docType: 'SHAREHOLDING_PATTERN', rawField: 'Promoter & Promoter Group', mappedTo: 'promoter_holding', value: '67%', confidence: 0.98 },
            { docType: 'BORROWING_PROFILE', rawField: 'HDFC Term Loan O/S', mappedTo: 'outstanding', value: '₹3.2 Cr', confidence: 0.93 },
            { docType: 'PORTFOLIO_CUTS', rawField: 'Overall GNPA', mappedTo: 'gross_npa_pct', value: '1.2%', confidence: 0.91 },
        ],
        sectorResearch: {
            outlook: 'POSITIVE', growth: '14% YoY',
            sub: 'CNC & automation booming on defence + EV manufacturing. Order books healthy.',
            macro: ['IIP: +6.2% YoY', 'Capital goods imports: -3%', 'Defence: ₹1.72L Cr (75% domestic)'],
            risks: ['CNC controller imports risk', 'Skilled labour shortage', 'Semiconductor disruption'],
        },
    },
};

const TICKER_ITEMS = [
    '🔴 RBI/2025-26/04: Revised LTV norms for MSME collateral — effective 01 Apr 2025',
    '🟡 GSTN Advisory: GSTR-2B auto-population delayed for Feb 2025 returns',
    '🔴 RBI FR-38 Compliance: Adverse action notices mandatory for all rejected corporate loans > ₹1 Cr',
    '🟢 MCA Update: Annual compliance filing deadline extended to 30 Apr 2025',
    '🟡 CIBIL: Commercial bureau data refresh cycle moved to T+2 from T+7',
    '🔴 RBI Circular: Increased risk weight on unsecured commercial loans — 150% from 100%',
];

const PILLAR_LABELS = ['Data Ingestor', 'Research Agent', 'CBM Engine', 'CAM Generator'];
const PILLAR_STATUS_TEXT = ['IDLE', 'RUNNING', 'COMPLETE'];

const SEV_COLORS = { CRIT: '#C8293A', WARN: '#C97C14', OK: '#25A05E', INFO: '#EDE5D4' };

const VIEW_SUBS = {
    brief: 'Pipeline & Flags',
    verdict: 'Score & Rationale',
    shap: 'Feature Weights',
    msme: 'GSTIN Scoring',
    swot: 'Analysis Matrix',
    classify: 'Doc Classification',
    triangulation: 'Cross-Reference',
    schema: 'Schema Mapping',
    dd: 'Analyst Review',
};

const INR_FORMATTER = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });

function formatCurrency(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
    return `₹${INR_FORMATTER.format(Number(value))}`;
}

function formatPercent(value, digits = 1) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
    return `${Number(value).toFixed(digits)}%`;
}

function getRiskColor(label) {
    if (!label) return 'var(--text-dim)';
    if (label.includes('VERY_LOW') || label.includes('LOW')) return 'var(--green)';
    if (label.includes('MODERATE')) return 'var(--amber)';
    return 'var(--red)';
}

function formatTimestamp(value) {
    if (!value) return 'N/A';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
    });
}

/* ─────────────────────── STYLES ─────────────────────── */
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#09080A;--gold:#C8A84B;--text:#EDE5D4;--text-dim:#9A9488;
  --red:#C8293A;--green:#25A05E;--amber:#C97C14;
  --card:#111012;--card-border:#1E1D1F;--sidebar-bg:#0D0C0E;
  --serif:'Cormorant Garamond',serif;--mono:'IBM Plex Mono',monospace;--body:'Libre Baskerville',serif;
}
body{background:var(--bg);color:var(--text);font-family:var(--body);overflow-x:hidden}
::selection{background:var(--gold);color:var(--bg)}
::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--gold);border-radius:0}

.ticker-wrap{width:100%;overflow:hidden;background:#0A0909;border-bottom:1px solid var(--card-border);height:28px;display:flex;align-items:center;position:relative;z-index:100}
.ticker{display:flex;animation:ticker 45s linear infinite;white-space:nowrap}
.ticker span{font-family:var(--mono);font-size:11px;color:var(--text-dim);padding:0 48px;letter-spacing:0.5px}
@keyframes ticker{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}

.topbar{display:flex;align-items:center;justify-content:space-between;padding:0 32px;height:48px;background:var(--sidebar-bg);border-bottom:1px solid var(--card-border)}
.topbar-left{display:flex;align-items:center;gap:24px}
.wordmark{font-family:var(--serif);font-size:18px;font-weight:700;color:var(--gold);letter-spacing:1px}
.wordmark span{font-family:var(--mono);font-weight:400;color:var(--text-dim);font-size:12px;margin-left:8px}
.session-id{font-family:var(--mono);font-size:9px;color:var(--text-dim);letter-spacing:1.5px;opacity:.6}
.scenario-btns{display:flex;gap:2px}
.scenario-btn{font-family:var(--mono);font-size:11px;padding:6px 16px;border:1px solid var(--card-border);background:transparent;color:var(--text-dim);cursor:pointer;text-transform:uppercase;letter-spacing:1px;transition:all .2s}
.scenario-btn.active{background:var(--gold);color:var(--bg);border-color:var(--gold);font-weight:600}
.scenario-btn.reject-accent{border-left:3px solid var(--red)}
.scenario-btn.approve-accent{border-left:3px solid var(--green)}
.scenario-btn:hover:not(.active){border-color:var(--gold);color:var(--gold)}
.avatar{width:32px;height:32px;background:var(--gold);display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:12px;font-weight:600;color:var(--bg)}

.layout{display:flex;height:calc(100vh - 76px)}
.sidebar{width:240px;min-width:240px;background:var(--sidebar-bg);border-right:1px solid var(--card-border);display:flex;flex-direction:column;padding:20px 16px;overflow-y:auto}
.main{flex:1;overflow-y:auto;padding:32px;position:relative}

.dossier-label{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:2px;color:var(--gold);margin-bottom:12px}
.dossier-company{font-family:var(--serif);font-size:22px;font-weight:700;color:var(--text);line-height:1.15;margin-bottom:2px}
.dossier-cin{font-family:var(--mono);font-size:9px;color:var(--text-dim);letter-spacing:.5px;margin-bottom:12px;opacity:.5}
.dossier-grid{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin-bottom:4px}
.dossier-key{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:1px;color:var(--text-dim);padding:3px 0}
.dossier-val{font-family:var(--mono);font-size:10px;color:var(--text);padding:3px 0}
.dossier-divider{width:100%;height:1px;background:var(--card-border);margin:14px 0}

.execute-wrap{position:relative;margin-bottom:16px}
.execute-btn{width:100%;padding:12px;font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;border:1px solid var(--gold);background:transparent;color:var(--gold);cursor:pointer;transition:all .3s;position:relative;overflow:hidden}
.execute-btn:hover:not(:disabled){background:var(--gold);color:var(--bg)}
.execute-btn:disabled{opacity:.5;cursor:not-allowed}
.execute-btn:disabled:hover{background:transparent;color:var(--gold)}
.progress-bar{position:absolute;bottom:0;left:0;height:2px;background:var(--gold);transition:none}
.progress-bar.active{animation:progressFill 7s linear forwards}
@keyframes progressFill{from{width:0}to{width:100%}}

.nav-item{font-family:var(--mono);font-size:11px;padding:8px 12px;color:var(--text-dim);cursor:pointer;border-left:2px solid transparent;transition:all .15s;letter-spacing:0.5px;text-transform:uppercase;margin-bottom:2px}
.nav-item:hover{color:var(--text);background:rgba(200,168,75,.05);border-left-color:rgba(200,168,75,.3)}
.nav-item.active{color:var(--gold);border-left-color:var(--gold);background:rgba(200,168,75,.06)}
.nav-sub{font-family:var(--mono);font-size:8px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim);opacity:.5;margin-top:2px;font-weight:400}
.nav-item.active .nav-sub{color:var(--gold);opacity:.6}

.pillar-section{margin-top:auto;padding-top:16px;border-top:1px solid var(--card-border)}
.pillar-label{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:2px;color:var(--text-dim);margin-bottom:10px}
.pillar-row{display:flex;align-items:center;justify-content:space-between;padding:5px 0;margin-bottom:2px;font-family:var(--mono);font-size:10px;color:var(--text-dim)}
.pillar-row-left{display:flex;align-items:center;gap:8px}
.pillar-dot{width:7px;height:7px;border-radius:50%}
.pillar-dot.idle{background:var(--card-border)}
.pillar-dot.processing{background:var(--amber);animation:pulse 1s ease-in-out infinite}
.pillar-dot.done{background:var(--green)}
.pillar-status{font-size:8px;letter-spacing:1px;text-transform:uppercase}
.pillar-status.idle-text{color:var(--text-dim);opacity:.4}
.pillar-status.running-text{color:var(--amber)}
.pillar-status.done-text{color:var(--green)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

.card{background:var(--card);border:1px solid var(--card-border);padding:24px;margin-bottom:20px}
.card-title{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--gold);margin-bottom:16px}

.fadein{animation:fadein .4s ease-out both}
@keyframes fadein{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}

.log-wrap{position:relative;overflow:hidden;background:var(--bg);border:1px solid var(--card-border)}
.log-wrap::before{content:'';position:absolute;inset:0;background:repeating-linear-gradient(0deg,transparent,transparent 19px,rgba(200,168,75,.03) 19px,rgba(200,168,75,.03) 20px);pointer-events:none;z-index:1}
.log-inner{position:relative;z-index:2;padding:10px 12px;overflow-y:auto}
.log-line{font-family:var(--mono);font-size:11px;line-height:1.8;white-space:pre-wrap}

.flags-banner{display:flex;align-items:center;gap:8px;padding:8px 12px;margin-bottom:12px;font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:1px}
.flags-banner.crit{background:rgba(200,41,58,.08);border:1px solid rgba(200,41,58,.2);color:var(--red)}
.flags-banner.ok{background:rgba(37,160,94,.06);border:1px solid rgba(37,160,94,.15);color:var(--green)}
.flag-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--card-border)}
.flag-row:last-child{border-bottom:none}
.flag-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.flag-source{font-family:var(--mono);font-size:8px;text-transform:uppercase;letter-spacing:1px;padding:2px 6px;border:1px solid var(--card-border);color:var(--text-dim);flex-shrink:0;min-width:56px;text-align:center}
.flag-text{font-family:var(--body);font-size:12px;color:var(--text-dim);line-height:1.4}

.score-giant{font-family:var(--serif);font-weight:700;font-size:120px;line-height:1}
.verdict-stamp{font-family:var(--mono);font-size:14px;font-weight:600;letter-spacing:4px;padding:8px 24px;border:2px solid;display:inline-block;margin-top:12px;text-transform:uppercase}

.bar-meter{height:3px;background:var(--card-border);position:relative;margin-top:6px;margin-bottom:16px}
.bar-fill{height:100%;position:absolute;left:0;top:0;transition:width 1s cubic-bezier(.16,1,.3,1)}
.bar-label{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--text-dim);display:flex;justify-content:space-between}

.shap-row{display:flex;align-items:center;margin-bottom:8px;height:28px}
.shap-label{width:220px;font-family:var(--mono);font-size:10px;color:var(--text-dim);text-align:right;padding-right:12px;flex-shrink:0}
.shap-bar-wrap{flex:1;position:relative;height:16px;display:flex;align-items:center}
.shap-center{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--card-border)}
.shap-bar{height:10px;position:absolute;transition:width .6s cubic-bezier(.16,1,.3,1)}

.factor-card{border-top:3px solid;padding:16px;background:var(--card);border-left:1px solid var(--card-border);border-right:1px solid var(--card-border);border-bottom:1px solid var(--card-border);flex:1}
.factor-label{font-family:var(--serif);font-size:15px;color:var(--text);margin-bottom:4px}
.factor-value{font-family:var(--mono);font-size:28px;font-weight:600}

.slider-group{margin-bottom:24px}
.slider-label{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim);margin-bottom:8px}
.slider-value{font-family:var(--serif);font-size:36px;font-weight:700;color:var(--gold)}
input[type=range]{-webkit-appearance:none;width:100%;height:3px;background:var(--card-border);outline:none;margin-top:8px}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;background:var(--gold);cursor:pointer}
textarea{width:100%;height:100px;background:var(--bg);border:1px solid var(--card-border);color:var(--text);font-family:var(--body);font-size:13px;padding:12px;resize:vertical}
textarea:focus{outline:none;border-color:var(--gold)}

.recalc-btn{padding:10px 32px;font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;border:1px solid var(--gold);background:var(--gold);color:var(--bg);cursor:pointer;margin-top:12px}
.recalc-btn:hover{background:transparent;color:var(--gold)}

.blockquote{border-left:3px solid var(--gold);padding:16px 20px;font-family:var(--body);font-style:italic;font-size:13.5px;line-height:1.7;color:var(--text-dim);margin-top:20px}

.sensitivity-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11px}
.sensitivity-table th{text-align:left;padding:8px;border-bottom:1px solid var(--card-border);color:var(--gold);text-transform:uppercase;letter-spacing:1px;font-size:9px}
.sensitivity-table td{padding:8px;border-bottom:1px solid var(--card-border);color:var(--text-dim)}

.compliance-box{border:1px solid var(--red);padding:16px;margin-top:16px;background:rgba(200,41,58,.04)}
.compliance-box h4{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--red);margin-bottom:8px}
.compliance-box p{font-family:var(--body);font-size:12px;color:var(--text-dim);line-height:1.6}

.processing-badge{font-family:var(--mono);font-size:10px;color:var(--amber);display:flex;align-items:center;gap:6px;margin-top:6px;margin-bottom:6px}
.processing-badge .dot{width:6px;height:6px;border-radius:50%;background:var(--amber);animation:pulse 1s ease-in-out infinite}

.two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.rate-row{display:flex;justify-content:space-between;font-family:var(--mono);font-size:12px;padding:4px 0;border-bottom:1px solid var(--card-border)}
.rate-row:last-child{border-bottom:none;font-weight:600;color:var(--gold)}

.swot-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.swot-cell{padding:20px;border:1px solid var(--card-border);background:var(--card)}
.swot-cell-header{font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;margin-bottom:12px;display:flex;align-items:center;gap:8px}
.swot-cell ul{list-style:none;padding:0}
.swot-cell li{font-family:var(--body);font-size:12px;line-height:1.6;color:var(--text-dim);padding:4px 0;border-bottom:1px solid rgba(30,29,31,.5)}
.swot-cell li:last-child{border-bottom:none}
.swot-cell li::before{content:'→ ';color:var(--text-dim);opacity:.4}

.classify-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11px}
.classify-table th{text-align:left;padding:10px 8px;border-bottom:1px solid var(--gold);color:var(--gold);text-transform:uppercase;letter-spacing:1px;font-size:9px}
.classify-table td{padding:10px 8px;border-bottom:1px solid var(--card-border);color:var(--text-dim)}
.classify-badge{font-family:var(--mono);font-size:9px;padding:3px 8px;letter-spacing:1px;text-transform:uppercase;display:inline-block}
.classify-badge.approved{background:rgba(37,160,94,.1);border:1px solid rgba(37,160,94,.3);color:var(--green)}
.classify-badge.edited{background:rgba(201,124,20,.1);border:1px solid rgba(201,124,20,.3);color:var(--amber)}
.classify-badge.rejected{background:rgba(200,41,58,.1);border:1px solid rgba(200,41,58,.3);color:var(--red)}
.classify-badge.pending{background:rgba(237,229,212,.05);border:1px solid var(--card-border);color:var(--text-dim)}

.tri-card{padding:16px;border:1px solid var(--card-border);background:var(--card);margin-bottom:12px}
.tri-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.tri-badge{font-family:var(--mono);font-size:9px;padding:3px 8px;letter-spacing:1px;text-transform:uppercase}
.tri-badge.aligned{background:rgba(37,160,94,.1);border:1px solid rgba(37,160,94,.3);color:var(--green)}
.tri-badge.contradicted{background:rgba(200,41,58,.1);border:1px solid rgba(200,41,58,.3);color:var(--red)}
.tri-badge.unverified{background:rgba(201,124,20,.1);border:1px solid rgba(201,124,20,.3);color:var(--amber)}
.tri-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:8px}
.tri-label{font-family:var(--mono);font-size:8px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim);margin-bottom:4px}
.tri-value{font-family:var(--body);font-size:12px;color:var(--text);line-height:1.5}
.tri-rec{font-family:var(--body);font-size:11px;color:var(--text-dim);font-style:italic;padding-top:8px;border-top:1px solid var(--card-border)}

.schema-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11px}
.schema-table th{text-align:left;padding:10px 8px;border-bottom:1px solid var(--gold);color:var(--gold);text-transform:uppercase;letter-spacing:1px;font-size:9px}
.schema-table td{padding:10px 8px;border-bottom:1px solid var(--card-border);color:var(--text-dim)}
.conf-bar{height:4px;background:var(--card-border);width:60px;display:inline-block;position:relative;vertical-align:middle;margin-left:6px}
.conf-fill{height:100%;position:absolute;left:0;top:0}

.loan-section{margin-top:4px}
.loan-label{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:2px;color:var(--gold);margin-bottom:8px;margin-top:12px}

.onboard-overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:1000;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(8px)}
.onboard-modal{background:var(--card);border:1px solid var(--card-border);width:640px;max-width:94vw;max-height:88vh;overflow-y:auto;position:relative}
.onboard-header{padding:24px 32px 16px;border-bottom:1px solid var(--card-border)}
.onboard-title{font-family:var(--serif);font-size:22px;font-weight:700;color:var(--gold)}
.onboard-subtitle{font-family:var(--mono);font-size:10px;color:var(--text-dim);margin-top:4px;letter-spacing:1px}
.onboard-steps{display:flex;gap:4px;margin-top:14px}
.onboard-step{flex:1;height:3px;background:var(--card-border);transition:background .3s}
.onboard-step.active{background:var(--gold)}
.onboard-step.done{background:var(--green)}
.onboard-body{padding:24px 32px}
.onboard-footer{padding:16px 32px;border-top:1px solid var(--card-border);display:flex;justify-content:space-between;align-items:center}
.onboard-field{margin-bottom:16px}
.onboard-field label{display:block;font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim);margin-bottom:6px}
.onboard-field input,.onboard-field select{width:100%;padding:10px 12px;background:var(--bg);border:1px solid var(--card-border);color:var(--text);font-family:var(--mono);font-size:12px}
.onboard-field input:focus,.onboard-field select:focus{outline:none;border-color:var(--gold)}
.onboard-two{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.onboard-btn{padding:10px 24px;font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;border:1px solid var(--gold);background:var(--gold);color:var(--bg);cursor:pointer;transition:all .2s}
.onboard-btn:hover{background:transparent;color:var(--gold)}
.onboard-btn.secondary{background:transparent;color:var(--text-dim);border-color:var(--card-border)}
.onboard-btn.secondary:hover{border-color:var(--gold);color:var(--gold)}
.onboard-skip{font-family:var(--mono);font-size:9px;color:var(--text-dim);cursor:pointer;letter-spacing:1px;opacity:.6;transition:opacity .2s}
.onboard-skip:hover{opacity:1;color:var(--gold)}

.agent-badges{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.agent-badge{font-family:var(--mono);font-size:9px;padding:4px 10px;letter-spacing:1px;text-transform:uppercase;display:inline-flex;align-items:center;gap:6px;border:1px solid var(--card-border)}
.agent-badge .badge-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.agent-badge.live .badge-dot{background:var(--green)}
.agent-badge.live{color:var(--green);border-color:rgba(37,160,94,.3)}
.agent-badge.cached .badge-dot{background:var(--amber)}
.agent-badge.cached{color:var(--amber);border-color:rgba(201,124,20,.3)}
.agent-badge.fallback .badge-dot{background:var(--red)}
.agent-badge.fallback{color:var(--red);border-color:rgba(200,41,58,.3)}
.agent-badge .badge-sync{font-size:7px;color:var(--text-dim);opacity:.6;margin-left:4px}

.override-panel{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.concept-override{padding:16px;border:1px solid var(--card-border);background:var(--card)}
.concept-override-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.concept-override-label{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim)}
.concept-override-scores{display:flex;gap:12px;align-items:baseline}
.concept-override-original{font-family:var(--mono);font-size:12px;color:var(--text-dim);text-decoration:line-through}
.concept-override-adjusted{font-family:var(--serif);font-size:24px;font-weight:700}
.override-note{width:100%;padding:8px;background:var(--bg);border:1px solid var(--card-border);color:var(--text);font-family:var(--mono);font-size:10px;margin-top:8px;resize:none;height:48px}
.override-note:focus{outline:none;border-color:var(--gold)}
.override-note::placeholder{color:var(--text-dim);opacity:.4}

.action-bar{display:flex;gap:8px;margin-top:16px}
.action-btn{padding:10px 24px;font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;border:1px solid;cursor:pointer;transition:all .2s}
.action-btn.approve-btn{border-color:var(--green);color:var(--green);background:transparent}
.action-btn.approve-btn:hover{background:var(--green);color:var(--bg)}
.action-btn.sendback-btn{border-color:var(--amber);color:var(--amber);background:transparent}
.action-btn.sendback-btn:hover{background:var(--amber);color:var(--bg)}
.action-btn.escalate-btn{border-color:var(--red);color:var(--red);background:transparent}
.action-btn.escalate-btn:hover{background:var(--red);color:var(--bg)}

.audit-entry{padding:12px;border:1px solid var(--card-border);background:var(--card);margin-bottom:8px;font-family:var(--mono);font-size:10px}
.audit-entry-header{display:flex;justify-content:space-between;margin-bottom:6px}
.audit-entry-time{color:var(--text-dim);font-size:9px}
.audit-entry-action{padding:2px 8px;font-size:8px;letter-spacing:1px;text-transform:uppercase}

.skeleton{background:linear-gradient(90deg,var(--card) 25%,var(--card-border) 50%,var(--card) 75%);background-size:200% 100%;animation:shimmer 1.5s ease-in-out infinite;border-radius:2px}
.skeleton-line{height:12px;margin-bottom:8px}
.skeleton-block{height:60px;margin-bottom:12px}
.skeleton-score{height:120px;width:200px;margin:0 auto 16px}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

.msme-score-display{text-align:center;padding:32px}
.msme-score-number{font-family:var(--serif);font-weight:700;font-size:96px;line-height:1}
.msme-score-scale{font-family:var(--mono);font-size:11px;color:var(--text-dim);margin-top:4px}
.msme-risk-band{font-family:var(--mono);font-size:13px;font-weight:600;letter-spacing:3px;padding:6px 20px;border:2px solid;display:inline-block;margin-top:16px;text-transform:uppercase}
.msme-gstin-input{display:flex;gap:8px;margin-bottom:20px}
.msme-gstin-input input{flex:1;padding:12px 16px;background:var(--bg);border:1px solid var(--card-border);color:var(--text);font-family:var(--mono);font-size:13px;letter-spacing:1px}
.msme-gstin-input input:focus{outline:none;border-color:var(--gold)}
.msme-gstin-input button{padding:12px 24px;font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;border:1px solid var(--gold);background:var(--gold);color:var(--bg);cursor:pointer}
.msme-gstin-input button:hover{background:transparent;color:var(--gold)}
.msme-gstin-input button:disabled{opacity:.5;cursor:not-allowed}

.signal-cards{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px}
.signal-card{padding:16px;border:1px solid var(--card-border);background:var(--card)}
.signal-card-title{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:2px;color:var(--gold);margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.signal-card-title .sparse-tag{font-size:7px;padding:2px 6px;background:rgba(201,124,20,.15);border:1px solid rgba(201,124,20,.3);color:var(--amber)}
.signal-metric{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(30,29,31,.5)}
.signal-metric:last-child{border-bottom:none}
.signal-metric-label{font-family:var(--mono);font-size:10px;color:var(--text-dim)}
.signal-metric-value{font-family:var(--mono);font-size:10px;font-weight:600}

.fraud-card{padding:20px;border:1px solid;margin-bottom:16px}
.fraud-card.high{border-color:var(--red);background:rgba(200,41,58,.04)}
.fraud-card.medium{border-color:var(--amber);background:rgba(201,124,20,.04)}
.fraud-card.low{border-color:var(--green);background:rgba(37,160,94,.04)}
.fraud-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.fraud-risk-badge{font-family:var(--mono);font-size:12px;font-weight:600;letter-spacing:2px}
.fraud-score{font-family:var(--serif);font-size:36px;font-weight:700}
.fraud-metrics{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.fraud-metric{text-align:center;padding:8px;border:1px solid var(--card-border)}
.fraud-metric-val{font-family:var(--mono);font-size:18px;font-weight:600}
.fraud-metric-label{font-family:var(--mono);font-size:8px;color:var(--text-dim);text-transform:uppercase;letter-spacing:1px;margin-top:2px}

.trend-chart{position:relative;height:200px;padding:20px 0;margin:16px 0}
.trend-chart-inner{display:flex;align-items:flex-end;gap:4px;height:160px;border-bottom:1px solid var(--card-border);border-left:1px solid var(--card-border);padding:0 8px 0 32px;position:relative}
.trend-bar-group{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px}
.trend-bar{width:100%;max-width:40px;transition:height .6s cubic-bezier(.16,1,.3,1);border-radius:2px 2px 0 0}
.trend-label{font-family:var(--mono);font-size:8px;color:var(--text-dim);transform:rotate(-45deg);white-space:nowrap}
.trend-score-label{font-family:var(--mono);font-size:9px;color:var(--text);margin-bottom:2px}
.trend-y-axis{position:absolute;left:0;top:0;bottom:20px;width:30px;display:flex;flex-direction:column;justify-content:space-between;font-family:var(--mono);font-size:8px;color:var(--text-dim)}

.reason-card{padding:12px 16px;border-left:3px solid;margin-bottom:8px;background:var(--card)}
.reason-card.positive{border-left-color:var(--green)}
.reason-card.negative{border-left-color:var(--red)}
.reason-text{font-family:var(--body);font-size:12px;color:var(--text-dim);line-height:1.5}
.reason-feature{font-family:var(--mono);font-size:9px;color:var(--text-dim);opacity:.6;margin-top:4px}

.freshness-stamp{font-family:var(--mono);font-size:9px;color:var(--text-dim);opacity:.6;display:flex;align-items:center;gap:6px;margin-top:12px}
.msme-empty{padding:32px;border:1px dashed var(--card-border);text-align:center;color:var(--text-dim);font-family:var(--body);font-size:13px;line-height:1.7}
.msme-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:20px}
.msme-meta{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
.msme-meta-card{padding:14px 16px;border:1px solid var(--card-border);background:rgba(237,229,212,.02)}
.msme-meta-label{font-family:var(--mono);font-size:8px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim);margin-bottom:6px}
.msme-meta-value{font-family:var(--body);font-size:12px;color:var(--text)}
.msme-sparse-note{margin-bottom:16px;padding:12px 14px;border:1px solid rgba(201,124,20,.25);background:rgba(201,124,20,.06);font-family:var(--body);font-size:12px;color:var(--text-dim);line-height:1.6}
.msme-error{margin-top:12px;padding:10px 12px;border:1px solid rgba(200,41,58,.25);background:rgba(200,41,58,.05);font-family:var(--mono);font-size:10px;color:var(--red)}
.msme-presets{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.msme-preset-btn{padding:8px 12px;border:1px solid var(--card-border);background:transparent;color:var(--text-dim);font-family:var(--mono);font-size:9px;letter-spacing:1px;text-transform:uppercase;cursor:pointer}
.msme-preset-btn:hover{border-color:var(--gold);color:var(--gold)}

@media (max-width: 1100px){
  .signal-cards,.fraud-metrics,.msme-meta,.two-col,.swot-grid,.override-panel,.tri-grid,.dropzone-grid,.onboard-two,.msme-grid{grid-template-columns:1fr}
}

@media (max-width: 768px){
  .topbar{padding:0 16px;gap:12px;height:auto;min-height:56px;flex-wrap:wrap}
  .layout{flex-direction:column;height:auto}
  .sidebar{width:100%;min-width:0;border-right:none;border-bottom:1px solid var(--card-border)}
  .main{padding:16px}
  .msme-gstin-input{flex-direction:column}
  .msme-score-number{font-size:72px}
}

.cam-download-btn{display:flex;align-items:center;gap:8px;padding:12px 24px;font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:2px;border:1px solid var(--gold);background:var(--gold);color:var(--bg);cursor:pointer;transition:all .2s;margin-top:16px;text-decoration:none}
.cam-download-btn:hover{background:transparent;color:var(--gold)}

.dropzone-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.dropzone-grid .dropzone-full{grid-column:1 / -1}
.dropzone{border:2px dashed var(--card-border);padding:20px;text-align:center;cursor:pointer;transition:all .2s;position:relative}
.dropzone:hover{border-color:var(--gold);background:rgba(200,168,75,.03)}
.dropzone.has-file{border-color:var(--green);border-style:solid;background:rgba(37,160,94,.04)}
.dropzone-type{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--gold);margin-bottom:4px}
.dropzone-hint{font-family:var(--mono);font-size:9px;color:var(--text-dim)}
.dropzone-file{font-family:var(--mono);font-size:10px;color:var(--green);margin-top:4px}
.dropzone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}
`;

/* ─────────────────────── COMPONENT ─────────────────────── */
export default function IntelliCreditDossier() {
    const [scenario, setScenario] = useState('reject');
    const [view, setView] = useState('brief');
    const [running, setRunning] = useState(false);
    const [done, setDone] = useState(false);
    const [logs, setLogs] = useState([]);
    const [animScore, setAnimScore] = useState(0);
    const [barsVisible, setBarsVisible] = useState(false);
    const [shapVisible, setShapVisible] = useState(false);
    const [mgmt, setMgmt] = useState(4);
    const [factory, setFactory] = useState(72);
    const [ddRecalc, setDdRecalc] = useState(false);
    const [pipelineProgress, setPipelineProgress] = useState(false);
    const logRef = useRef(null);
    const timersRef = useRef([]);

    // Onboarding state
    const [onboardingComplete, setOnboardingComplete] = useState(false);
    const [obStep, setObStep] = useState(1); // 1=Entity, 2=Loan, 3=Upload
    const [obEntity, setObEntity] = useState({ company: '', cin: '', pan: '', sector: '', promoter: '', vintage: '', cibil: '' });
    const [obLoan, setObLoan] = useState({ type: 'Working Capital', amount: '', tenure: '', rate: '' });
    const [obFiles, setObFiles] = useState({ ALM: null, SHAREHOLDING: null, BORROWING: null, ANNUAL_REPORT: null, PORTFOLIO: null });

    // Live data from real backend pipeline
    const [liveData, setLiveData] = useState(null);

    // Agent source status badges
    const [agentStatus, setAgentStatus] = useState({
        mca: { source_status: 'cached', last_synced: '2025-12-15T10:30:00Z' },
        ecourts: { source_status: 'cached', last_synced: '2025-12-15T11:00:00Z' },
        rbi_watchlist: { source_status: 'cached', last_synced: '2025-12-15T11:15:00Z' },
        news: { source_status: 'cached', last_synced: '2025-12-15T11:30:00Z' },
    });

    // MSME GSTIN scoring state
    const [gstinInput, setGstinInput] = useState('');
    const [msmeScoring, setMsmeScoring] = useState(false);
    const [msmeResult, setMsmeResult] = useState(null);
    const [msmeError, setMsmeError] = useState('');

    // Analyst override state
    const [conceptOverrides, setConceptOverrides] = useState({});
    const [overrideNotes, setOverrideNotes] = useState({});
    const [fieldNotes, setFieldNotes] = useState('');
    const [reviewAction, setReviewAction] = useState(null);
    const [auditTrail, setAuditTrail] = useState([]);

    const data = liveData || SCENARIOS[scenario];

    const resetAll = useCallback(() => {
        timersRef.current.forEach(clearTimeout);
        timersRef.current = [];
        setRunning(false); setDone(false); setLogs([]);
        setAnimScore(0); setBarsVisible(false); setShapVisible(false);
        setMgmt(4); setFactory(72); setDdRecalc(false); setPipelineProgress(false);
    }, []);

    const switchScenario = (s) => {
        setScenario(s);
        setLiveData(null); // Clear live data on demo switch
        resetAll();
        setView('brief');
        setOnboardingComplete(true);
        setMsmeError('');
        setGstinInput(s === 'reject' ? '27ARJUN1234A1Z5' : '29CLEAN5678B1Z2');
    };

    const executePipeline = async () => {
        if (running || done) return;
        resetAll();
        setRunning(true);
        setPipelineProgress(true);

        const isRealUpload = Object.values(obFiles).some(f => f !== null);

        if (isRealUpload) {
            // Live API Flow
            try {
                // First simulate fast logs to keep UI engaging while backend processes
                const baseLogs = [
                    { t: 400, sev: 'INFO', msg: '[L1] Uploading documents for processing…' },
                    { t: 1200, sev: 'INFO', msg: '[L1] Parsing PDFs and extracting tables…' },
                    { t: 2500, sev: 'INFO', msg: '[L1] Indexing new document chunks to ChromaDB…' },
                    { t: 4000, sev: 'INFO', msg: '[L2] Running agentic web search (Tavily)…' },
                    { t: 6000, sev: 'INFO', msg: '[L3] Reconciling internal vs external data…' },
                    { t: 8000, sev: 'INFO', msg: '[SYN] Awaiting LLM narrative and CBM scoring…' },
                ];

                baseLogs.forEach((entry) => {
                    const tid = setTimeout(() => {
                        setLogs(prev => [...prev, entry]);
                        if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
                    }, entry.t);
                    timersRef.current.push(tid);
                });

                // Prepare FormData
                const formData = new FormData();
                if (obFiles.ALM) formData.append('alm', obFiles.ALM);
                if (obFiles.SHAREHOLDING) formData.append('shareholding', obFiles.SHAREHOLDING);
                if (obFiles.BORROWING) formData.append('borrowing_profile', obFiles.BORROWING);
                if (obFiles.ANNUAL_REPORT) formData.append('annual_report', obFiles.ANNUAL_REPORT);
                if (obFiles.PORTFOLIO) formData.append('portfolio_cuts', obFiles.PORTFOLIO);
                formData.append('borrower_name', obEntity.company || 'Unknown Entity');

                // Call API
                const resp = await fetch(`${API_BASE_URL}/api/pipeline/run`, {
                    method: 'POST',
                    headers: buildApiHeaders(),
                    body: formData,
                });

                if (!resp.ok) throw new Error('Pipeline API failed');

                const result = await resp.json();

                // Construct standard frontend shape from API result
                const formattedRecord = {
                    company: obEntity.company || 'Unknown Entity',
                    cin: obEntity.cin || 'N/A',
                    sector: obEntity.sector || 'N/A',
                    vintage: obEntity.vintage || 'N/A',
                    promoter: obEntity.promoter || 'N/A',
                    pan: obEntity.pan || 'N/A',
                    turnover: 'Actuals Used',
                    cibil: obEntity.cibil || 'N/A',
                    score: result.score || 50,
                    verdict: result.verdict || 'REJECT',
                    limit: obLoan.amount,
                    rate: { base: 8.5, risk: 1.5, sector: 0, total: 10.0 }, // Mocked for now
                    rationale: result.rationale || 'Score derived from five C model execution.',
                    fiveCs: {
                        Character: result.concept_scores?.Character || 0.5,
                        Capacity: result.concept_scores?.Capacity || 0.5,
                        Capital: result.concept_scores?.Capital || 0.5,
                        Collateral: result.concept_scores?.Collateral || 0.5,
                        Conditions: result.concept_scores?.Conditions || 0.5,
                    },
                    loan: obLoan,
                    shap: (result.shap_top_factors || []).map(s => ({
                        feature: s.feature.replace(/_/g, ' '),
                        value: s.importance,
                        color: s.importance > 0 ? '#25A05E' : '#C8293A'
                    })),
                    pipeline: result.cam_sections?.overview ? [
                        { t: 100, sev: 'OK', msg: 'Real pipeline execution finished.' },
                        { t: 300, sev: 'INFO', msg: 'CAM DOCX generated and ready for download.' }
                    ] : [],
                    contradictions: [],
                    riskFlags: Object.entries(result.concept_flags || {}).filter(([k, v]) => v).map(([k, v]) => ({
                        sev: 'WARN', source: k, text: typeof v === 'string' ? v : JSON.stringify(v)
                    })),
                    devil: result.devils_advocate || 'No override analysis generated.',
                    swot: result.cam_sections?.swot || { strengths: [], weaknesses: [], opportunities: [], threats: [] },
                    classification: Object.entries(obFiles).filter(([k, v]) => v).map(([k, v]) => ({
                        filename: v.name, predicted: k, confidence: 1.0, evidence: 'User Uploaded', corrected: null, status: 'APPROVED'
                    })),
                    triangulation: result.cam_sections?.triangulation?.findings || [],
                    schemaMappings: [],
                    sectorResearch: null
                };

                // Clear fake logs and inject real data
                timersRef.current.forEach(clearTimeout);
                setLogs([]);
                setLiveData(formattedRecord);
                setRunning(false);
                setDone(true);

            } catch (err) {
                console.error(err);
                setLogs([{ t: 100, sev: 'CRIT', msg: `Pipeline Error: ${err.message}` }]);
                setRunning(false);
                setDone(true);
            }
        } else {
            // Demo Scenario Flow (Simulated timing)
            data.pipeline.forEach((entry) => {
                const tid = setTimeout(() => {
                    setLogs(prev => [...prev, entry]);
                    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
                }, entry.t);
                timersRef.current.push(tid);
            });
            const finishTid = setTimeout(() => { setRunning(false); setDone(true); }, 7000);
            timersRef.current.push(finishTid);

            // Fetch agent status badges
            try {
                const statusResp = await fetch(`${API_BASE_URL}/api/agent-status/${encodeURIComponent(data.company)}`, {
                    headers: buildApiHeaders(),
                });
                if (statusResp.ok) {
                    const statusData = await statusResp.json();
                    setAgentStatus(statusData.agents || agentStatus);
                }
            } catch { /* Backend not running — use defaults */ }
        }
    };

    const runMsmeScoring = async () => {
        const normalizedGstin = gstinInput.trim().toUpperCase();
        if (!normalizedGstin) {
            setMsmeError('Enter a GSTIN to run MSME scoring.');
            return;
        }
        if (normalizedGstin.length < 5) {
            setMsmeError('GSTIN looks too short. Use a valid GSTIN-like identifier.');
            return;
        }

        setMsmeScoring(true);
        setMsmeError('');

        try {
            const companyQuery = obEntity.company ? `?company_name=${encodeURIComponent(obEntity.company)}` : '';
            const resp = await fetch(`${API_BASE_URL}/api/score/${encodeURIComponent(normalizedGstin)}${companyQuery}`, {
                method: 'POST',
                headers: buildApiHeaders(),
            });

            if (!resp.ok) {
                const message = await resp.text();
                throw new Error(message || 'Scoring request failed');
            }

            const result = await resp.json();
            setMsmeResult(result);
            setGstinInput(normalizedGstin);
        } catch (err) {
            setMsmeError(err instanceof Error ? err.message : 'Unable to score GSTIN right now.');
        } finally {
            setMsmeScoring(false);
        }
    };

    useEffect(() => {
        if (!done) return;
        const target = data.score;
        const duration = 1600;
        const start = performance.now();
        let raf;
        const animate = (now) => {
            const t = Math.min((now - start) / duration, 1);
            const ease = 1 - Math.pow(1 - t, 3);
            setAnimScore(+(ease * target).toFixed(1));
            if (t < 1) raf = requestAnimationFrame(animate);
        };
        raf = requestAnimationFrame(animate);
        const barTid = setTimeout(() => setBarsVisible(true), 400);
        const shapTid = setTimeout(() => setShapVisible(true), 800);
        timersRef.current.push(barTid, shapTid);
        return () => cancelAnimationFrame(raf);
    }, [done, data.score]);

    const isReject = data.verdict === 'REJECT';
    const scoreColor = isReject ? 'var(--red)' : 'var(--green)';

    const pillarStates = !running && !done ? [0, 0, 0, 0] : running ? (() => {
        const n = logs.length;
        if (n < 4) return [1, 0, 0, 0];
        if (n < 8) return [2, 1, 0, 0];
        if (n < 12) return [2, 2, 1, 0];
        return [2, 2, 2, 1];
    })() : [2, 2, 2, 2];

    const VIEWS = ['brief', 'verdict', 'shap', 'msme', 'swot', 'classify', 'triangulation', 'schema', 'dd'];
    const VIEW_LABELS = ['Intelligence Brief', 'Verdict', 'SHAP Attribution', 'MSME Scoring', 'SWOT Analysis', 'Classification', 'Triangulation', 'Schema Mapping', 'Analyst Review'];

    const hasCritFlags = data.riskFlags.some(f => f.sev === 'CRIT' || f.sev === 'WARN');
    const msmeRiskBand = msmeResult?.risk_band?.band || '';
    const msmeRiskColor = getRiskColor(msmeRiskBand);
    const scoreHistory = msmeResult?.score_history || [];
    const trendBars = scoreHistory.slice(-6);
    const signalEntries = msmeResult?.pipeline_signals
        ? [
            {
                key: 'gst',
                title: 'GST Velocity',
                sparse: msmeResult.pipeline_signals.gst_velocity.sparse_data,
                metrics: [
                    ['Filing Rate', `${msmeResult.pipeline_signals.gst_velocity.filing_rate}/mo`],
                    ['Avg Delay', `${msmeResult.pipeline_signals.gst_velocity.avg_delay} days`],
                    ['On-Time', formatPercent(msmeResult.pipeline_signals.gst_velocity.on_time_pct)],
                    ['E-Invoice Trend', msmeResult.pipeline_signals.gst_velocity.e_invoice_trend],
                ],
            },
            {
                key: 'upi',
                title: 'UPI Cadence',
                sparse: msmeResult.pipeline_signals.upi_cadence.sparse_data,
                metrics: [
                    ['Daily Txns', `${msmeResult.pipeline_signals.upi_cadence.avg_daily_txns}`],
                    ['Regularity', `${msmeResult.pipeline_signals.upi_cadence.regularity_score}/100`],
                    ['Inflow/Outflow', `${msmeResult.pipeline_signals.upi_cadence.inflow_outflow_ratio}x`],
                    ['Round Amounts', formatPercent(msmeResult.pipeline_signals.upi_cadence.round_amount_pct)],
                ],
            },
            {
                key: 'eway',
                title: 'E-Way Bill Volume',
                sparse: msmeResult.pipeline_signals.eway_bill.sparse_data,
                metrics: [
                    ['Monthly Bills', `${msmeResult.pipeline_signals.eway_bill.avg_monthly_bills}`],
                    ['Momentum', formatPercent(msmeResult.pipeline_signals.eway_bill.volume_momentum)],
                    ['Interstate', formatPercent(msmeResult.pipeline_signals.eway_bill.interstate_ratio)],
                    ['Anomalies', `${msmeResult.pipeline_signals.eway_bill.anomaly_count}`],
                ],
            },
        ]
        : [];

    return (
        <>
            <style>{CSS}</style>

            {/* ─── Ticker ─── */}
            <div className="ticker-wrap">
                <div className="ticker">
                    {[...TICKER_ITEMS, ...TICKER_ITEMS].map((t, i) => <span key={i}>{t}</span>)}
                </div>
            </div>

            {/* ─── Onboarding Modal ─── */}
            {!onboardingComplete && (
                <div className="onboard-overlay">
                    <div className="onboard-modal">
                        <div className="onboard-header">
                            <div className="onboard-title">New Credit Appraisal</div>
                            <div className="onboard-subtitle">STEP {obStep} OF 3 — {obStep === 1 ? 'ENTITY DETAILS' : obStep === 2 ? 'LOAN DETAILS' : 'DOCUMENT UPLOAD'}</div>
                            <div className="onboard-steps">
                                <div className={`onboard-step ${obStep >= 1 ? 'active' : ''} ${obStep > 1 ? 'done' : ''}`} />
                                <div className={`onboard-step ${obStep >= 2 ? 'active' : ''} ${obStep > 2 ? 'done' : ''}`} />
                                <div className={`onboard-step ${obStep >= 3 ? 'active' : ''}`} />
                            </div>
                        </div>
                        <div className="onboard-body">
                            {obStep === 1 && (
                                <>
                                    <div className="onboard-two">
                                        <div className="onboard-field"><label>Company Name</label><input value={obEntity.company} onChange={e => setObEntity({ ...obEntity, company: e.target.value })} placeholder="e.g. Arjun Textiles Pvt. Ltd." /></div>
                                        <div className="onboard-field"><label>CIN</label><input value={obEntity.cin} onChange={e => setObEntity({ ...obEntity, cin: e.target.value })} placeholder="U17111MH2019PTC012345" /></div>
                                    </div>
                                    <div className="onboard-two">
                                        <div className="onboard-field"><label>PAN</label><input value={obEntity.pan} onChange={e => setObEntity({ ...obEntity, pan: e.target.value })} placeholder="AABCA1234Z" /></div>
                                        <div className="onboard-field"><label>Sector</label><input value={obEntity.sector} onChange={e => setObEntity({ ...obEntity, sector: e.target.value })} placeholder="Textiles — Spinning & Weaving" /></div>
                                    </div>
                                    <div className="onboard-two">
                                        <div className="onboard-field"><label>Promoter Name</label><input value={obEntity.promoter} onChange={e => setObEntity({ ...obEntity, promoter: e.target.value })} placeholder="Arjun Singhania" /></div>
                                        <div className="onboard-field"><label>Vintage</label><input value={obEntity.vintage} onChange={e => setObEntity({ ...obEntity, vintage: e.target.value })} placeholder="5 years" /></div>
                                    </div>
                                    <div className="onboard-field"><label>CIBIL CMR</label><input value={obEntity.cibil} onChange={e => setObEntity({ ...obEntity, cibil: e.target.value })} placeholder="CMR-6 (Below Average)" /></div>
                                </>
                            )}
                            {obStep === 2 && (
                                <>
                                    <div className="onboard-two">
                                        <div className="onboard-field">
                                            <label>Loan Type</label>
                                            <select value={obLoan.type} onChange={e => setObLoan({ ...obLoan, type: e.target.value })}>
                                                <option>Working Capital</option>
                                                <option>Term Loan</option>
                                                <option>OD/CC Limit</option>
                                                <option>Letter of Credit</option>
                                                <option>Bank Guarantee</option>
                                            </select>
                                        </div>
                                        <div className="onboard-field"><label>Loan Amount</label><input value={obLoan.amount} onChange={e => setObLoan({ ...obLoan, amount: e.target.value })} placeholder="₹3.00 Cr" /></div>
                                    </div>
                                    <div className="onboard-two">
                                        <div className="onboard-field"><label>Tenure</label><input value={obLoan.tenure} onChange={e => setObLoan({ ...obLoan, tenure: e.target.value })} placeholder="12 months" /></div>
                                        <div className="onboard-field"><label>Expected Rate</label><input value={obLoan.rate} onChange={e => setObLoan({ ...obLoan, rate: e.target.value })} placeholder="14.2%" /></div>
                                    </div>
                                </>
                            )}
                            {obStep === 3 && (
                                <>
                                    <div className="dropzone-grid">
                                        {[
                                            { key: 'ANNUAL_REPORT', label: 'Annual Report (P&L, BS, CF)', accept: '.pdf,.xlsx,.csv', full: true },
                                            { key: 'ALM', label: 'ALM Statement', accept: '.csv,.xlsx' },
                                            { key: 'SHAREHOLDING', label: 'Shareholding Pattern', accept: '.csv,.xlsx' },
                                            { key: 'BORROWING', label: 'Borrowing Profile', accept: '.csv,.xlsx' },
                                            { key: 'PORTFOLIO', label: 'Portfolio Cuts / Performance', accept: '.csv,.xlsx' },
                                        ].map(slot => (
                                            <div key={slot.key} className={`dropzone ${slot.full ? 'dropzone-full' : ''} ${obFiles[slot.key] ? 'has-file' : ''}`}>
                                                <div className="dropzone-type">{slot.label}</div>
                                                {obFiles[slot.key]
                                                    ? <div className="dropzone-file">✓ {obFiles[slot.key].name}</div>
                                                    : <div className="dropzone-hint">Drop file here or click to browse — {slot.accept}</div>
                                                }
                                                <input type="file" accept={slot.accept} onChange={e => {
                                                    if (e.target.files[0]) setObFiles(prev => ({ ...prev, [slot.key]: e.target.files[0] }));
                                                }} />
                                            </div>
                                        ))}
                                    </div>
                                </>
                            )}
                        </div>
                        <div className="onboard-footer">
                            <div>
                                {obStep > 1 && <button className="onboard-btn secondary" onClick={() => setObStep(s => s - 1)}>← Back</button>}
                            </div>
                            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                                <span className="onboard-skip" onClick={() => { setOnboardingComplete(true); switchScenario('reject'); }}>Skip — use demo data</span>
                                {obStep < 3
                                    ? <button className="onboard-btn" onClick={() => setObStep(s => s + 1)}>Next →</button>
                                    : <button className="onboard-btn" onClick={() => { setOnboardingComplete(true); executePipeline(); }}>Begin Analysis ▶</button>
                                }
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ─── Top Bar ─── */}
            <div className="topbar">
                <div className="topbar-left">
                    <div className="wordmark">INTELLI<span style={{ color: 'var(--gold)' }}>CREDIT</span><span>v1.0 — AI Credit Engine</span></div>
                    <div className="session-id">SESSION: IC-20260306-0042</div>
                </div>
                <div className="scenario-btns">
                    <button className={`scenario-btn reject-accent ${scenario === 'reject' ? 'active' : ''}`} onClick={() => switchScenario('reject')}>▪ Reject Scenario</button>
                    <button className={`scenario-btn approve-accent ${scenario === 'approve' ? 'active' : ''}`} onClick={() => switchScenario('approve')}>▪ Approve Scenario</button>
                </div>
                <div className="avatar">VM</div>
            </div>

            {/* ─── Layout ─── */}
            <div className="layout">
                {/* ─── Sidebar ─── */}
                <div className="sidebar">
                    <div className="dossier-label">Borrower Dossier</div>
                    <div className="dossier-company">{data.company}</div>
                    <div className="dossier-cin">{data.cin}</div>
                    <div className="dossier-grid">
                        <div className="dossier-key">Sector</div><div className="dossier-val">{data.sector}</div>
                        <div className="dossier-key">Vintage</div><div className="dossier-val">{data.vintage}</div>
                        <div className="dossier-key">Promoter</div><div className="dossier-val">{data.promoter}</div>
                        <div className="dossier-key">PAN</div><div className="dossier-val">{data.pan}</div>
                        <div className="dossier-key">Turnover</div><div className="dossier-val">{data.turnover}</div>
                        <div className="dossier-key">CIBIL</div><div className="dossier-val">{data.cibil}</div>
                    </div>
                    {data.loan && (
                        <div className="loan-section">
                            <div className="loan-label">Loan Request</div>
                            <div className="dossier-grid">
                                <div className="dossier-key">Type</div><div className="dossier-val">{data.loan.type}</div>
                                <div className="dossier-key">Amount</div><div className="dossier-val" style={{ color: 'var(--gold)' }}>{data.loan.amount}</div>
                                <div className="dossier-key">Tenure</div><div className="dossier-val">{data.loan.tenure}</div>
                                <div className="dossier-key">Rate</div><div className="dossier-val">{data.loan.rate}</div>
                            </div>
                        </div>
                    )}
                    <div className="dossier-divider" />

                    <div className="execute-wrap">
                        <button className="execute-btn" onClick={executePipeline} disabled={running || done}>
                            {running ? '● Processing…' : done ? '✓ Complete' : '▶ Execute Pipeline'}
                        </button>
                        {pipelineProgress && !done && <div className="progress-bar active" />}
                        {done && <div className="progress-bar" style={{ width: '100%', background: 'var(--green)' }} />}
                    </div>
                    {running && <div className="processing-badge"><span className="dot" /> PROCESSING</div>}

                    <div className="dossier-divider" />
                    {VIEWS.map((v, i) => (
                        <div key={v} className={`nav-item ${view === v ? 'active' : ''}`} onClick={() => setView(v)}>
                            <div>{VIEW_LABELS[i]}</div>
                            <div className="nav-sub">{VIEW_SUBS[v]}</div>
                        </div>
                    ))}

                    <div className="pillar-section">
                        <div className="pillar-label">Pipeline Status</div>
                        {PILLAR_LABELS.map((p, i) => (
                            <div className="pillar-row" key={p}>
                                <div className="pillar-row-left">
                                    <div className={`pillar-dot ${pillarStates[i] === 0 ? 'idle' : pillarStates[i] === 1 ? 'processing' : 'done'}`} />
                                    <span>{p}</span>
                                </div>
                                <span className={`pillar-status ${pillarStates[i] === 0 ? 'idle-text' : pillarStates[i] === 1 ? 'running-text' : 'done-text'}`}>
                                    {PILLAR_STATUS_TEXT[pillarStates[i]]}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* ─── Main Content ─── */}
                <div className="main">

                    {/* ===== INTELLIGENCE BRIEF ===== */}
                    {view === 'brief' && (
                        <div className="fadein" key="brief">
                            <div className="two-col">
                                <div className="card">
                                    <div className="card-title">Pipeline Execution Log</div>
                                    <div className="log-wrap" style={{ maxHeight: 280 }}>
                                        <div className="log-inner" ref={logRef} style={{ maxHeight: 280, overflowY: 'auto' }}>
                                            {logs.length === 0 && <div className="log-line" style={{ color: 'var(--text-dim)' }}>Awaiting pipeline execution…</div>}
                                            {logs.map((l, i) => (
                                                <div className="log-line" key={i} style={{ color: SEV_COLORS[l.sev] }}>
                                                    <span style={{ color: 'var(--text-dim)', marginRight: 8 }}>{new Date(Date.now()).toLocaleTimeString()}</span>
                                                    <span style={{ fontWeight: 600, marginRight: 8 }}>[{l.sev}]</span>
                                                    {l.msg.replace(/^\[\w+\]\s*/, '')}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                                <div className="card">
                                    <div className="card-title">Risk Flags</div>
                                    <div className="agent-badges">
                                        {Object.entries(agentStatus).map(([key, val]) => {
                                            const labels = { mca: 'MCA', ecourts: 'eCourts', rbi_watchlist: 'RBI', news: 'News' };
                                            const status = val.source_status || 'cached';
                                            const syncDate = val.last_synced ? new Date(val.last_synced).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' }) : '';
                                            return (
                                                <div key={key} className={`agent-badge ${status}`}>
                                                    <span className="badge-dot" />
                                                    {labels[key]}: {status.toUpperCase()}
                                                    {syncDate && <span className="badge-sync">{syncDate}</span>}
                                                </div>
                                            );
                                        })}
                                    </div>
                                    <div className={`flags-banner ${hasCritFlags ? 'crit' : 'ok'}`}>
                                        {hasCritFlags ? '⚠' : '✓'} {hasCritFlags ? `${data.riskFlags.length} FLAGS DETECTED` : 'NO CRITICAL FLAGS'}
                                    </div>
                                    {data.riskFlags.map((f, i) => (
                                        <div className="flag-row" key={i}>
                                            <div className="flag-dot" style={{ background: SEV_COLORS[f.sev] }} />
                                            <div className="flag-source">{f.source}</div>
                                            <div className="flag-text">{f.text}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Contradictions — always shown for reject, message for approve */}
                            <div className="card fadein">
                                <div className="card-title" style={{ color: data.contradictions.length > 0 ? 'var(--amber)' : 'var(--green)' }}>
                                    {data.contradictions.length > 0 ? '⚠ Contradictions Detector — Cross-Pillar Reconciliation' : '✓ Contradictions Detector — All Pillars Reconciled'}
                                </div>
                                {data.contradictions.length > 0 ? data.contradictions.map((c, i) => (
                                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 16, padding: '16px 0', borderBottom: '1px solid var(--card-border)' }}>
                                        <div>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>GST Filings</div>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 18, color: 'var(--amber)', marginTop: 4 }}>{c.val1}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>Bank Credits</div>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 18, color: 'var(--red)', marginTop: 4 }}>{c.val2}</div>
                                        </div>
                                        <div>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>Annual Report</div>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 18, color: 'var(--amber)', marginTop: 4 }}>{c.val3}</div>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', flexDirection: 'column', justifyContent: 'center' }}>
                                            <span style={{ fontFamily: 'var(--mono)', fontSize: 24, fontWeight: 700, color: 'var(--red)' }}>{c.gap}</span>
                                            <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--text-dim)', letterSpacing: 2 }}>GAP</span>
                                        </div>
                                    </div>
                                )) : (
                                    <div style={{ fontFamily: 'var(--body)', fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                                        GST turnover (₹41.8 Cr), bank statement credits (₹42.1 Cr), and annual report revenue (₹42.5 Cr) reconcile within 2% tolerance. No irreconcilable gaps detected across verification pillars.
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* ===== VERDICT ===== */}
                    {view === 'verdict' && (
                        <div className="fadein" key="verdict">
                            <div className="two-col">
                                <div className="card" style={{ textAlign: 'center', paddingTop: 40, paddingBottom: 40 }}>
                                    {!done && running && (
                                        <div>
                                            <div className="skeleton skeleton-score" />
                                            <div className="skeleton skeleton-line" style={{ width: '40%', margin: '0 auto' }} />
                                        </div>
                                    )}
                                    {!running && !done && (
                                        <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--text-dim)' }}>
                                            Execute pipeline to generate score
                                        </div>
                                    )}
                                    {(done || (!running && !done)) && <div className="score-giant" style={{ color: scoreColor, textShadow: `0 0 60px ${scoreColor}40` }}>{done ? animScore : '—'}</div>}
                                    {(done || (!running && !done)) && <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-dim)', marginTop: 8 }}>/ 100</div>}
                                    {done && <div className="verdict-stamp" style={{ borderColor: scoreColor, color: scoreColor, marginTop: 20 }}>{data.verdict}</div>}
                                    {done && data.verdict === 'APPROVE' && (
                                        <div style={{ marginTop: 24, textAlign: 'left' }}>
                                            <div className="card-title">Sanction Parameters</div>
                                            <div className="rate-row"><span>Recommended Limit</span><span style={{ color: 'var(--gold)' }}>{data.limit}</span></div>
                                            <div className="rate-row"><span>Base Rate (MCLR)</span><span>{data.rate.base}%</span></div>
                                            <div className="rate-row"><span>CBM Risk Premium</span><span>+{data.rate.risk}%</span></div>
                                            <div className="rate-row"><span>Sector Spread</span><span>{data.rate.sector}%</span></div>
                                            <div className="rate-row"><span>Final Interest Rate</span><span>{data.rate.total}%</span></div>
                                        </div>
                                    )}
                                    {done && data.verdict === 'REJECT' && (
                                        <div className="compliance-box" style={{ marginTop: 24, textAlign: 'left' }}>
                                            <h4>RBI FR-38 Adverse Action Notice</h4>
                                            <p>Pursuant to RBI Master Direction DOR.STR.REC.10/21.04.048/2025-26, the application for credit facility has been declined. Primary factors: (1) Material revenue discrepancy across verification pillars; (2) Active debt recovery proceedings; (3) Adverse bureau score below institutional threshold. The applicant retains the right to request a copy of the credit report used in this assessment.</p>
                                        </div>
                                    )}
                                </div>
                                <div className="card">
                                    <div className="card-title">Five C's of Credit</div>
                                    {Object.entries(data.fiveCs).map(([label, val], idx) => {
                                        const pct = val * 100;
                                        const col = pct >= 75 ? 'var(--green)' : pct >= 50 ? 'var(--amber)' : 'var(--red)';
                                        return (
                                            <div key={label}>
                                                <div className="bar-label"><span>{label}</span><span>{done ? `${pct.toFixed(0)}%` : '—'}</span></div>
                                                <div className="bar-meter"><div className="bar-fill" style={{ width: barsVisible ? `${pct}%` : '0%', background: col, transitionDelay: `${idx * 120}ms` }} /></div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                            {done && <div className="blockquote">{data.rationale}</div>}
                            {done && (
                                <a className="cam-download-btn" href={withAuthQuery(`${API_BASE_URL}/api/download/CAM_${(data.company || '').replace(/\s+/g, '_')}.docx`)} target="_blank" rel="noopener noreferrer">
                                    Download CAM Report (DOCX)
                                </a>
                            )}
                        </div>
                    )}

                    {/* ===== SHAP ===== */}
                    {view === 'shap' && (
                        <div className="fadein" key="shap">
                            <div className="card">
                                <div className="card-title">SHAP Feature Attribution — Waterfall</div>
                                <div style={{ padding: '12px 0' }}>
                                    {data.shap.map((s, i) => {
                                        const maxAbsVal = 0.20;
                                        const barWidthPct = Math.min(Math.abs(s.value) / maxAbsVal * 45, 45);
                                        const isNeg = s.value < 0;
                                        return (
                                            <div className="shap-row" key={i}>
                                                <div className="shap-label">{s.feature}</div>
                                                <div className="shap-bar-wrap">
                                                    <div className="shap-center" />
                                                    <div className="shap-bar" style={{
                                                        width: shapVisible ? `${barWidthPct}%` : '0%',
                                                        background: s.color,
                                                        left: isNeg ? `${50 - barWidthPct}%` : '50%',
                                                        transitionDelay: `${i * 80}ms`,
                                                        opacity: 0.8,
                                                    }} />
                                                </div>
                                                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: s.color, minWidth: 48, textAlign: 'right' }}>
                                                    {s.value > 0 ? '+' : ''}{s.value.toFixed(2)}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: 16 }}>
                                {data.shap.slice(0, 3).map((s, i) => (
                                    <div className="factor-card" key={i} style={{ borderTopColor: s.color }}>
                                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Top Factor #{i + 1}</div>
                                        <div className="factor-label">{s.feature}</div>
                                        <div className="factor-value" style={{ color: s.color }}>{s.value > 0 ? '+' : ''}{s.value.toFixed(2)}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* ===== MSME GSTIN SCORING ===== */}
                    {view === 'msme' && (
                        <div className="fadein" key="msme">
                            <div className="card">
                                <div className="card-title">GSTIN-Based MSME Scoring</div>
                                <div className="msme-gstin-input">
                                    <input
                                        value={gstinInput}
                                        onChange={e => {
                                            setGstinInput(e.target.value.toUpperCase());
                                            if (msmeError) setMsmeError('');
                                        }}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter') runMsmeScoring();
                                        }}
                                        placeholder={scenario === 'reject' ? '27ARJUN1234A1Z5' : '29CLEAN5678B1Z2'}
                                    />
                                    <button onClick={runMsmeScoring} disabled={msmeScoring}>
                                        {msmeScoring ? 'Scoring…' : 'Score GSTIN'}
                                    </button>
                                </div>
                                <div style={{ fontFamily: 'var(--body)', fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.6 }}>
                                    Runs the mock GST velocity, UPI cadence, and e-way bill pipelines, engineers sparse-safe time-series features, scores on a 300-900 scale, and returns SHAP-based reasons plus a loan recommendation.
                                </div>
                                <div className="msme-presets">
                                    <button className="msme-preset-btn" onClick={() => setGstinInput('29CLEAN5678B1Z2')}>Use Clean Demo</button>
                                    <button className="msme-preset-btn" onClick={() => setGstinInput('27ARJUN1234A1Z5')}>Use Reject Demo</button>
                                    <button className="msme-preset-btn" onClick={() => setGstinInput('09NEWCO1234A1Z9')}>Use 3-Month Demo</button>
                                </div>
                                {msmeError && <div className="msme-error">{msmeError}</div>}
                            </div>

                            {!msmeResult && !msmeScoring && (
                                <div className="msme-empty">
                                    Enter a GSTIN-like identifier to generate the new problem-statement-aligned MSME scorecard. The response includes a 300-900 score, risk band, top-5 reasons, fraud signals, recommendation, and score trend history.
                                </div>
                            )}

                            {msmeScoring && (
                                <div className="card">
                                    <div className="skeleton skeleton-score" />
                                    <div className="skeleton skeleton-line" style={{ width: '55%' }} />
                                    <div className="skeleton skeleton-line" style={{ width: '80%' }} />
                                    <div className="skeleton skeleton-block" />
                                </div>
                            )}

                            {msmeResult && !msmeScoring && (
                                <>
                                    {msmeResult.data_sparse && (
                                        <div className="msme-sparse-note">
                                            Sparse history detected. The scoring flow is blending observed values with population defaults so a 3-month borrower still gets a usable assessment, with confidence penalties reflected in the reasons and score.
                                        </div>
                                    )}

                                    <div className="msme-grid">
                                        <div>
                                            <div className="card">
                                                <div className="card-title">Scorecard</div>
                                                <div className="msme-score-display">
                                                    <div className="msme-score-number" style={{ color: msmeRiskColor, textShadow: `0 0 60px ${msmeRiskColor}40` }}>
                                                        {msmeResult.credit_score}
                                                    </div>
                                                    <div className="msme-score-scale">/ 900</div>
                                                    <div className="msme-risk-band" style={{ borderColor: msmeRiskColor, color: msmeRiskColor }}>
                                                        {msmeRiskBand.replaceAll('_', ' ')}
                                                    </div>
                                                    <div className="freshness-stamp" style={{ justifyContent: 'center' }}>
                                                        Freshness: {formatTimestamp(msmeResult.score_freshness)}
                                                    </div>
                                                </div>
                                                <div className="msme-meta">
                                                    <div className="msme-meta-card">
                                                        <div className="msme-meta-label">Entity</div>
                                                        <div className="msme-meta-value">{msmeResult.company_name}</div>
                                                    </div>
                                                    <div className="msme-meta-card">
                                                        <div className="msme-meta-label">GSTIN</div>
                                                        <div className="msme-meta-value" style={{ fontFamily: 'var(--mono)' }}>{msmeResult.gstin}</div>
                                                    </div>
                                                    <div className="msme-meta-card">
                                                        <div className="msme-meta-label">Model</div>
                                                        <div className="msme-meta-value">{msmeResult.model_version}</div>
                                                    </div>
                                                    <div className="msme-meta-card">
                                                        <div className="msme-meta-label">Band Description</div>
                                                        <div className="msme-meta-value">{msmeResult.risk_band?.description}</div>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="card">
                                                <div className="card-title">Score Trend</div>
                                                <div className="trend-chart">
                                                    <div className="trend-y-axis">
                                                        <span>900</span>
                                                        <span>700</span>
                                                        <span>500</span>
                                                        <span>300</span>
                                                    </div>
                                                    <div className="trend-chart-inner">
                                                        {trendBars.map((entry, idx) => {
                                                            const height = Math.max(16, ((entry.score - 300) / 600) * 150);
                                                            const color = getRiskColor(entry.risk_band);
                                                            return (
                                                                <div className="trend-bar-group" key={`${entry.timestamp}-${idx}`}>
                                                                    <div className="trend-score-label">{entry.score}</div>
                                                                    <div className="trend-bar" style={{ height, background: color, opacity: entry.fraud_risk === 'HIGH' ? 0.7 : 1 }} />
                                                                    <div className="trend-label">
                                                                        {new Date(entry.timestamp).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })}
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="card">
                                                <div className="card-title">Top-5 SHAP Reasons</div>
                                                {msmeResult.top_reasons.map((reason, idx) => (
                                                    <div className={`reason-card ${reason.direction}`} key={`${reason.feature}-${idx}`}>
                                                        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: reason.direction === 'positive' ? 'var(--green)' : 'var(--red)', marginBottom: 6 }}>
                                                            {reason.feature}
                                                        </div>
                                                        <div className="reason-text">{reason.reason}</div>
                                                        <div className="reason-feature">
                                                            SHAP {reason.shap_value > 0 ? '+' : ''}{reason.shap_value} | Feature Value: {reason.feature_value}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        <div>
                                            <div className="card">
                                                <div className="card-title">Loan Recommendation</div>
                                                <div className={`flags-banner ${msmeResult.recommendation?.eligible ? 'ok' : 'crit'}`}>
                                                    {msmeResult.recommendation?.eligible ? '✓ ELIGIBLE FOR CREDIT' : '⚠ CURRENTLY INELIGIBLE'}
                                                </div>
                                                <div className="rate-row"><span>Recommended Amount</span><span style={{ color: 'var(--gold)' }}>{formatCurrency(msmeResult.recommendation?.recommended_amount)}</span></div>
                                                <div className="rate-row"><span>Tenure</span><span>{msmeResult.recommendation?.recommended_tenure_months || 0} months</span></div>
                                                <div className="rate-row"><span>Indicative Rate</span><span>{msmeResult.recommendation?.indicative_rate_pct ?? 'N/A'}{msmeResult.recommendation?.indicative_rate_pct !== null && msmeResult.recommendation?.indicative_rate_pct !== undefined ? '%' : ''}</span></div>
                                                <div className="rate-row"><span>Base Rate</span><span>{msmeResult.recommendation?.base_rate ?? 'N/A'}{msmeResult.recommendation?.base_rate !== null && msmeResult.recommendation?.base_rate !== undefined ? '%' : ''}</span></div>
                                                <div className="rate-row"><span>Risk Premium</span><span>{msmeResult.recommendation?.risk_premium ?? 'N/A'}{msmeResult.recommendation?.risk_premium !== null && msmeResult.recommendation?.risk_premium !== undefined ? '%' : ''}</span></div>
                                                {!msmeResult.recommendation?.eligible && msmeResult.recommendation?.reason && (
                                                    <div className="blockquote" style={{ marginTop: 16 }}>{msmeResult.recommendation.reason}</div>
                                                )}
                                            </div>

                                            <div className={`fraud-card ${(msmeResult.fraud_detection?.circular_risk || 'LOW').toLowerCase()}`}>
                                                <div className="fraud-header">
                                                    <div>
                                                        <div className="card-title" style={{ marginBottom: 6 }}>UPI Circular Flow Detection</div>
                                                        <div className="fraud-risk-badge" style={{ color: getRiskColor(msmeResult.fraud_detection?.circular_risk || '') }}>
                                                            {(msmeResult.fraud_detection?.circular_risk || 'LOW')} RISK
                                                        </div>
                                                    </div>
                                                    <div className="fraud-score">{msmeResult.fraud_detection?.risk_score || 0}</div>
                                                </div>
                                                <div className="fraud-metrics">
                                                    <div className="fraud-metric">
                                                        <div className="fraud-metric-val">{msmeResult.fraud_detection?.cycle_count || 0}</div>
                                                        <div className="fraud-metric-label">Cycles</div>
                                                    </div>
                                                    <div className="fraud-metric">
                                                        <div className="fraud-metric-val">{msmeResult.fraud_detection?.bounceback_count || 0}</div>
                                                        <div className="fraud-metric-label">Bouncebacks</div>
                                                    </div>
                                                    <div className="fraud-metric">
                                                        <div className="fraud-metric-val">{formatPercent(msmeResult.fraud_detection?.round_amount_pct || 0)}</div>
                                                        <div className="fraud-metric-label">Round Amounts</div>
                                                    </div>
                                                </div>
                                                <div className="freshness-stamp">
                                                    Counterparties: {msmeResult.fraud_detection?.counterparty_count || 0} | Linked MSMEs: {msmeResult.fraud_detection?.linked_msme_count || 0} | Total Volume: {formatCurrency(msmeResult.fraud_detection?.total_volume || 0)}
                                                </div>
                                            </div>

                                            <div className="card">
                                                <div className="card-title">Real-Time Signal Pipelines</div>
                                                <div className="signal-cards">
                                                    {signalEntries.map(signal => (
                                                        <div className="signal-card" key={signal.key}>
                                                            <div className="signal-card-title">
                                                                <span>{signal.title}</span>
                                                                {signal.sparse && <span className="sparse-tag">SPARSE</span>}
                                                            </div>
                                                            {signal.metrics.map(([label, value]) => (
                                                                <div className="signal-metric" key={label}>
                                                                    <span className="signal-metric-label">{label}</span>
                                                                    <span className="signal-metric-value">{value}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                    )}

                    {/* ===== ANALYST REVIEW (HITL) ===== */}
                    {view === 'dd' && (
                        <div className="fadein" key="dd">
                            {/* Concept Score Overrides */}
                            <div className="card">
                                <div className="card-title">Concept Score Overrides — Analyst Review</div>
                                <div style={{ fontFamily: 'var(--body)', fontSize: 12, color: 'var(--text-dim)', marginBottom: 16, lineHeight: 1.6 }}>
                                    Adjust any concept score with a mandatory note. Overrides exceeding 10 points require Branch Head sign-off.
                                </div>
                                <div className="override-panel">
                                    {Object.entries(data.fiveCs).map(([concept, val]) => {
                                        const pct = val * 100;
                                        const overridden = conceptOverrides[concept] !== undefined;
                                        const currentVal = overridden ? conceptOverrides[concept] : pct;
                                        const col = currentVal >= 75 ? 'var(--green)' : currentVal >= 50 ? 'var(--amber)' : 'var(--red)';
                                        return (
                                            <div className="concept-override" key={concept}>
                                                <div className="concept-override-header">
                                                    <div className="concept-override-label">{concept}</div>
                                                    <div className="concept-override-scores">
                                                        {overridden && <span className="concept-override-original">{pct.toFixed(0)}%</span>}
                                                        <span className="concept-override-adjusted" style={{ color: col }}>{currentVal.toFixed(0)}%</span>
                                                    </div>
                                                </div>
                                                <input type="range" min="0" max="100" step="1" value={currentVal}
                                                    onChange={e => {
                                                        const newVal = +e.target.value;
                                                        setConceptOverrides(prev => ({ ...prev, [concept]: newVal }));
                                                        setDdRecalc(false);
                                                    }}
                                                />
                                                <textarea
                                                    className="override-note"
                                                    placeholder={`Reason for ${concept} adjustment (required)...`}
                                                    value={overrideNotes[concept] || ''}
                                                    onChange={e => setOverrideNotes(prev => ({ ...prev, [concept]: e.target.value }))}
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="two-col">
                                {/* DD Qualitative Inputs */}
                                <div className="card">
                                    <div className="card-title">Due Diligence — Field Observations</div>
                                    <div className="slider-group">
                                        <div className="slider-label">Management Quality</div>
                                        <div className="slider-value">{mgmt}/5</div>
                                        <input type="range" min="1" max="5" step="1" value={mgmt} onChange={e => { setMgmt(+e.target.value); setDdRecalc(false) }} />
                                    </div>
                                    <div className="slider-group">
                                        <div className="slider-label">Factory Utilisation</div>
                                        <div className="slider-value">{factory}%</div>
                                        <input type="range" min="0" max="100" step="1" value={factory} onChange={e => { setFactory(+e.target.value); setDdRecalc(false) }} />
                                    </div>
                                    <textarea placeholder="Field observations, site visit notes, management interaction summary…" value={fieldNotes} onChange={e => setFieldNotes(e.target.value)} />
                                    <button className="recalc-btn" onClick={() => setDdRecalc(true)}>Recalculate Score</button>
                                </div>

                                <div>
                                    {/* Devil's Advocate */}
                                    <div className="card">
                                        <div className="card-title">Devil's Advocate AI</div>
                                        <div style={{ fontFamily: 'var(--body)', fontSize: 13, lineHeight: 1.7, color: 'var(--text-dim)', fontStyle: 'italic' }}>
                                            {data.devil}
                                        </div>
                                        {ddRecalc && (() => {
                                            const overrideAdj = Object.entries(conceptOverrides).reduce((sum, [k, v]) => sum + (v - (data.fiveCs[k] || 0) * 100) * 0.2, 0);
                                            const ddAdj = (mgmt >= 3 ? 2 : -4) + (factory >= 60 ? 1 : -2);
                                            const revisedScore = Math.max(0, Math.min(100, (data.score + overrideAdj + ddAdj)));
                                            return (
                                                <table className="sensitivity-table" style={{ marginTop: 16 }}>
                                                    <thead><tr><th>Metric</th><th>Model</th><th>Adjustment</th><th>Revised</th></tr></thead>
                                                    <tbody>
                                                        <tr>
                                                            <td>CBM Score</td>
                                                            <td>{data.score}</td>
                                                            <td style={{ color: overrideAdj >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                                                {overrideAdj >= 0 ? '+' : ''}{overrideAdj.toFixed(1)}
                                                            </td>
                                                            <td style={{ color: revisedScore >= 60 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                                                                {revisedScore.toFixed(1)}
                                                            </td>
                                                        </tr>
                                                        <tr>
                                                            <td>Mgmt Quality</td>
                                                            <td>—</td>
                                                            <td style={{ color: mgmt >= 3 ? 'var(--green)' : 'var(--amber)' }}>{mgmt >= 3 ? '+2.0' : '-4.0'}</td>
                                                            <td>—</td>
                                                        </tr>
                                                        <tr>
                                                            <td>Factory Util.</td>
                                                            <td>—</td>
                                                            <td style={{ color: factory >= 60 ? 'var(--green)' : 'var(--amber)' }}>{factory >= 60 ? '+1.0' : '-2.0'}</td>
                                                            <td>—</td>
                                                        </tr>
                                                        {Object.entries(conceptOverrides).filter(([k, v]) => v !== (data.fiveCs[k] || 0) * 100).map(([k, v]) => (
                                                            <tr key={k}>
                                                                <td>{k} Override</td>
                                                                <td>{((data.fiveCs[k] || 0) * 100).toFixed(0)}%</td>
                                                                <td style={{ color: v > (data.fiveCs[k] || 0) * 100 ? 'var(--green)' : 'var(--red)' }}>
                                                                    → {v.toFixed(0)}%
                                                                </td>
                                                                <td style={{ fontSize: 9, color: 'var(--text-dim)' }}>{overrideNotes[k] || 'No reason'}</td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            );
                                        })()}
                                    </div>

                                    {/* Compliance */}
                                    <div className="compliance-box">
                                        <h4>RBI FR-38 Compliance Reminder</h4>
                                        <p>All qualitative overrides must be documented with rationale per RBI Master Direction DOR.STR.REC.10/21.04.048/2025-26. Overrides exceeding ±10% of quantitative score require Branch Head sign-off. Deviations must be reported in the quarterly CRILC submission.</p>
                                    </div>
                                </div>
                            </div>

                            {/* Action Buttons */}
                            <div className="card">
                                <div className="card-title">Analyst Decision</div>
                                <div className="action-bar">
                                    <button className="action-btn approve-btn" onClick={async () => {
                                        setReviewAction('APPROVE');
                                        const overrides = Object.entries(conceptOverrides)
                                            .filter(([k, v]) => v !== (data.fiveCs[k] || 0) * 100)
                                            .map(([k, v]) => ({
                                                concept: k,
                                                original_score: (data.fiveCs[k] || 0) * 100,
                                                adjusted_score: v,
                                                reason: overrideNotes[k] || 'No reason provided',
                                                action: 'ADJUST',
                                            }));
                                        const payload = {
                                            session_id: 'IC-20260306-0042',
                                            company_name: data.company,
                                            original_score: data.score,
                                            overrides,
                                            management_quality: mgmt,
                                            factory_utilization: factory,
                                            field_notes: fieldNotes,
                                            action: 'APPROVE',
                                        };
                                        try {
                                            const resp = await fetch(`${API_BASE_URL}/api/analyst/review`, {
                                                method: 'POST',
                                                headers: buildApiHeaders({ 'Content-Type': 'application/json' }),
                                                body: JSON.stringify(payload),
                                            });
                                            if (resp.ok) {
                                                const result = await resp.json();
                                                setAuditTrail(prev => [...prev, result.audit_entry]);
                                            }
                                        } catch { setAuditTrail(prev => [...prev, { ...payload, timestamp: new Date().toISOString(), adjusted_score: data.score, analyst_action: 'APPROVE' }]); }
                                    }}>
                                        Approve CAM
                                    </button>
                                    <button className="action-btn sendback-btn" onClick={() => {
                                        setReviewAction('SEND_BACK');
                                        setAuditTrail(prev => [...prev, { timestamp: new Date().toISOString(), analyst_action: 'SEND_BACK', company_name: data.company, original_score: data.score, field_notes: fieldNotes }]);
                                    }}>
                                        Send Back
                                    </button>
                                    <button className="action-btn escalate-btn" onClick={() => {
                                        setReviewAction('ESCALATE');
                                        setAuditTrail(prev => [...prev, { timestamp: new Date().toISOString(), analyst_action: 'ESCALATE', company_name: data.company, original_score: data.score, field_notes: fieldNotes }]);
                                    }}>
                                        Escalate to Branch Head
                                    </button>
                                </div>
                                {reviewAction && (
                                    <div style={{ marginTop: 12, fontFamily: 'var(--mono)', fontSize: 11, color: reviewAction === 'APPROVE' ? 'var(--green)' : reviewAction === 'SEND_BACK' ? 'var(--amber)' : 'var(--red)' }}>
                                        Decision recorded: {reviewAction}
                                    </div>
                                )}
                            </div>

                            {/* Audit Trail */}
                            {auditTrail.length > 0 && (
                                <div className="card">
                                    <div className="card-title">Audit Trail</div>
                                    {auditTrail.map((entry, i) => (
                                        <div className="audit-entry" key={i}>
                                            <div className="audit-entry-header">
                                                <span className={`audit-entry-action classify-badge ${entry.analyst_action === 'APPROVE' ? 'approved' : entry.analyst_action === 'SEND_BACK' ? 'edited' : 'rejected'}`}>
                                                    {entry.analyst_action}
                                                </span>
                                                <span className="audit-entry-time">{new Date(entry.timestamp).toLocaleString()}</span>
                                            </div>
                                            <div style={{ color: 'var(--text-dim)', marginTop: 4 }}>
                                                Model: {entry.original_score} → Adjusted: {entry.adjusted_score || entry.original_score}
                                                {entry.field_notes && <span style={{ marginLeft: 8 }}>| Notes: {entry.field_notes.substring(0, 80)}{entry.field_notes.length > 80 ? '...' : ''}</span>}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* ===== SWOT ANALYSIS ===== */}
                    {view === 'swot' && data.swot && (
                        <div className="fadein" key="swot">
                            <div className="card">
                                <div className="card-title">SWOT Analysis — AI-Generated (Grounded on Extracted Data)</div>
                                {data.sectorResearch && (
                                    <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
                                        <div className="factor-card" style={{ borderTopColor: data.sectorResearch.outlook === 'POSITIVE' ? 'var(--green)' : data.sectorResearch.outlook === 'NEGATIVE' ? 'var(--red)' : 'var(--amber)', flex: '0 0 auto', minWidth: 160 }}>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>Sector Outlook</div>
                                            <div className="factor-label">{data.sectorResearch.outlook}</div>
                                            <div style={{ fontFamily: 'var(--mono)', fontSize: 14, color: 'var(--gold)' }}>{data.sectorResearch.growth}</div>
                                        </div>
                                        <div style={{ flex: 1, fontFamily: 'var(--body)', fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7, padding: '8px 0' }}>
                                            {data.sectorResearch.sub}
                                        </div>
                                    </div>
                                )}
                            </div>
                            <div className="swot-grid">
                                <div className="swot-cell">
                                    <div className="swot-cell-header" style={{ color: 'var(--green)' }}>◆ Strengths</div>
                                    <ul>{data.swot.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
                                </div>
                                <div className="swot-cell">
                                    <div className="swot-cell-header" style={{ color: 'var(--red)' }}>◆ Weaknesses</div>
                                    <ul>{data.swot.weaknesses.map((w, i) => <li key={i}>{w}</li>)}</ul>
                                </div>
                                <div className="swot-cell">
                                    <div className="swot-cell-header" style={{ color: 'var(--gold)' }}>◆ Opportunities</div>
                                    <ul>{data.swot.opportunities.map((o, i) => <li key={i}>{o}</li>)}</ul>
                                </div>
                                <div className="swot-cell">
                                    <div className="swot-cell-header" style={{ color: 'var(--amber)' }}>◆ Threats</div>
                                    <ul>{data.swot.threats.map((t, i) => <li key={i}>{t}</li>)}</ul>
                                </div>
                            </div>
                            {data.sectorResearch && (
                                <div className="card" style={{ marginTop: 16 }}>
                                    <div className="card-title">Macro Indicators</div>
                                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                        {data.sectorResearch.macro.map((m, i) => (
                                            <div key={i} style={{ fontFamily: 'var(--mono)', fontSize: 11, padding: '6px 12px', border: '1px solid var(--card-border)', color: 'var(--text-dim)' }}>{m}</div>
                                        ))}
                                    </div>
                                    <div style={{ marginTop: 12 }}>
                                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Sector Risk Factors</div>
                                        {data.sectorResearch.risks.map((r, i) => (
                                            <div key={i} style={{ fontFamily: 'var(--body)', fontSize: 12, color: 'var(--text-dim)', padding: '3px 0' }}>• {r}</div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ===== CLASSIFICATION (HITL) ===== */}
                    {view === 'classify' && data.classification && (
                        <div className="fadein" key="classify">
                            <div className="card">
                                <div className="card-title">Document Classification — Human-in-the-Loop Review</div>
                                <div className={`flags-banner ${data.classification.some(c => c.status === 'EDITED' || c.status === 'PENDING') ? 'crit' : 'ok'}`}>
                                    {data.classification.some(c => c.status === 'EDITED' || c.status === 'PENDING')
                                        ? `⚠ ${data.classification.filter(c => c.status === 'EDITED').length} RECLASSIFIED BY ANALYST`
                                        : '✓ ALL CLASSIFICATIONS APPROVED'}
                                </div>
                                <table className="classify-table">
                                    <thead><tr>
                                        <th>File Name</th>
                                        <th>AI Prediction</th>
                                        <th>Confidence</th>
                                        <th>Evidence</th>
                                        <th>Final Type</th>
                                        <th>Status</th>
                                    </tr></thead>
                                    <tbody>
                                        {data.classification.map((c, i) => (
                                            <tr key={i}>
                                                <td style={{ color: 'var(--text)', fontSize: 10 }}>{c.filename}</td>
                                                <td>{c.predicted.replace(/_/g, ' ')}</td>
                                                <td>
                                                    <span style={{ color: c.confidence >= 0.8 ? 'var(--green)' : c.confidence >= 0.6 ? 'var(--amber)' : 'var(--red)' }}>
                                                        {(c.confidence * 100).toFixed(0)}%
                                                    </span>
                                                </td>
                                                <td style={{ fontSize: 10 }}>{c.evidence}</td>
                                                <td style={{ fontWeight: 600, color: c.corrected ? 'var(--amber)' : 'var(--text-dim)' }}>
                                                    {(c.corrected || c.predicted).replace(/_/g, ' ')}
                                                </td>
                                                <td><span className={`classify-badge ${c.status.toLowerCase()}`}>{c.status}</span></td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            <div className="blockquote">
                                Documents are auto-classified using filename heuristics and content keyword detection. The analyst reviews and confirms each classification before the extraction pipeline runs. Reclassified documents are re-routed to the correct parser.
                            </div>
                        </div>
                    )}

                    {/* ===== TRIANGULATION ===== */}
                    {view === 'triangulation' && data.triangulation && (
                        <div className="fadein" key="triangulation">
                            <div className="card">
                                <div className="card-title">Data Triangulation — External vs Internal Cross-Reference</div>
                                <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                                    {['ALIGNED', 'CONTRADICTED', 'UNVERIFIED'].map(type => {
                                        const count = data.triangulation.filter(t => t.alignment === type).length;
                                        const col = type === 'ALIGNED' ? 'var(--green)' : type === 'CONTRADICTED' ? 'var(--red)' : 'var(--amber)';
                                        return (
                                            <div key={type} className="factor-card" style={{ borderTopColor: col }}>
                                                <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: 1 }}>{type}</div>
                                                <div className="factor-value" style={{ color: col }}>{count}</div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                            {data.triangulation.map((t, i) => (
                                <div className="tri-card" key={i}>
                                    <div className="tri-header">
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <div className="flag-dot" style={{ background: SEV_COLORS[t.sev] }} />
                                            <span className={`tri-badge ${t.alignment.toLowerCase()}`}>{t.alignment}</span>
                                        </div>
                                        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--text-dim)', letterSpacing: 1 }}>[{t.sev}]</span>
                                    </div>
                                    <div className="tri-grid">
                                        <div>
                                            <div className="tri-label">External Signal</div>
                                            <div className="tri-value">{t.external}</div>
                                        </div>
                                        <div>
                                            <div className="tri-label">Internal Data Point</div>
                                            <div className="tri-value">{t.internal}</div>
                                        </div>
                                    </div>
                                    <div className="tri-rec">💡 {t.rec}</div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* ===== SCHEMA MAPPING ===== */}
                    {view === 'schema' && data.schemaMappings && (
                        <div className="fadein" key="schema">
                            <div className="card">
                                <div className="card-title">Schema Mapping Visibility — Raw Field → Structured Output</div>
                                <table className="schema-table">
                                    <thead><tr>
                                        <th>Document Type</th>
                                        <th>Raw Field</th>
                                        <th>→ Mapped To</th>
                                        <th>Extracted Value</th>
                                        <th>Confidence</th>
                                    </tr></thead>
                                    <tbody>
                                        {data.schemaMappings.map((m, i) => (
                                            <tr key={i}>
                                                <td style={{ fontSize: 9 }}>{m.docType.replace(/_/g, ' ')}</td>
                                                <td style={{ color: 'var(--text)' }}>{m.rawField}</td>
                                                <td style={{ color: 'var(--gold)', fontWeight: 600 }}>{m.mappedTo}</td>
                                                <td style={{ color: 'var(--text)' }}>{m.value}</td>
                                                <td>
                                                    <span style={{ color: m.confidence >= 0.9 ? 'var(--green)' : 'var(--amber)' }}>{(m.confidence * 100).toFixed(0)}%</span>
                                                    <span className="conf-bar"><span className="conf-fill" style={{ width: `${m.confidence * 100}%`, background: m.confidence >= 0.9 ? 'var(--green)' : 'var(--amber)' }} /></span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            <div className="blockquote">
                                Schema mappings show how raw document fields are transformed into structured extraction output. Analysts can configure the target schema per document type via the backend API (PUT /api/schema/{'{doc_type}'}). Confidence scores reflect the extraction engine's certainty in each mapping.
                            </div>
                        </div>
                    )}

                </div>
            </div>
        </>
    );
}
