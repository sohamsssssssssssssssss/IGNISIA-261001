import React, { Suspense, lazy, useEffect, useMemo, useState } from 'react';
import { Search, Loader2, RotateCcw, Download } from 'lucide-react';
import { ScoreHero } from './ScoreHero';
import { LoanRecommendation } from './LoanRecommendation';
import { ScoringProgress } from './ScoringProgress';
import { gstinValidationMessage, normalizeGstin } from './gstin';
import { DataSourceBanner } from './DataSourceBanner';
import { ModelMetricsPanel } from './ModelMetricsPanel';
import { RuntimeStatusBanner } from './RuntimeStatusBanner';
import ChatPanel from './ChatPanel';
import NarrativeSummary from './NarrativeSummary';
import SimilarCasesPanel from './SimilarCasesPanel';

const ShapWaterfall = lazy(() => import('./ShapWaterfall').then(module => ({ default: module.ShapWaterfall })));
const PipelineSignals = lazy(() => import('./PipelineSignals').then(module => ({ default: module.PipelineSignals })));
const ScoreTrend = lazy(() => import('./ScoreTrend').then(module => ({ default: module.ScoreTrend })));
const FraudDetection = lazy(() => import('./FraudDetection').then(module => ({ default: module.FraudDetection })));
const EntityGraph = lazy(() => import('./EntityGraph').then(module => ({ default: module.EntityGraph })));
const ConfidencePanel = lazy(() => import('./ConfidencePanel').then(module => ({ default: module.ConfidencePanel })));
const FeatureVectorTable = lazy(() => import('./FeatureVectorTable').then(module => ({ default: module.FeatureVectorTable })));
const ScoreImprovementSimulator = lazy(() => import('./ScoreImprovementSimulator').then(module => ({ default: module.ScoreImprovementSimulator })));
const AuditTrailPanel = lazy(() => import('./AuditTrailPanel').then(module => ({ default: module.AuditTrailPanel })));
const SparseDataChecklist = lazy(() => import('./SparseDataChecklist').then(module => ({ default: module.SparseDataChecklist })));
const ComparisonPanel = lazy(() => import('./ComparisonPanel').then(module => ({ default: module.ComparisonPanel })));

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';
const SCORING_STEPS = [
  'Validate GSTIN',
  'Ingest GST / UPI / E-Way signals',
  'Engineer sparse-safe features',
  'Score with gradient boosting',
  'Generate SHAP explanations',
];

function buildHeaders(): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (API_TOKEN) h['Authorization'] = `Bearer ${API_TOKEN}`;
  return h;
}

function withAuthQuery(url: string): string {
  if (!API_TOKEN) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${encodeURIComponent(API_TOKEN)}`;
}

const DEMO_GSTINS = [
  { gstin: '29CLEAN5678B1Z2', label: 'Approve', company: 'CleanTech Mfg' },
  { gstin: '27ARJUN1234A1Z5', label: 'Reject + Fraud', company: 'Arjun Textiles' },
  { gstin: '09NEWCO1234A1Z9', label: 'Sparse Data', company: 'New Startup' },
];

interface MSMEScoringProps {
  showTopbar?: boolean;
}

function parseNarrativeText(value: string | null | undefined) {
  const text = (value || '').trim();
  if (!text) return null;
  const paragraphs = text.split(/\n\s*\n/).map((item) => item.trim()).filter(Boolean);
  if (paragraphs.length >= 3) {
    return {
      businessOverview: paragraphs[0],
      keyRiskFactors: paragraphs[1],
      recommendation: paragraphs[2],
    };
  }
  const sentences = text.split(/(?<=[.!?])\s+/).map((item) => item.trim()).filter(Boolean);
  if (sentences.length >= 3) {
    const firstCut = Math.max(1, Math.floor(sentences.length / 3));
    const secondCut = Math.max(firstCut + 1, Math.floor((2 * sentences.length) / 3));
    return {
      businessOverview: sentences.slice(0, firstCut).join(' '),
      keyRiskFactors: sentences.slice(firstCut, secondCut).join(' '),
      recommendation: sentences.slice(secondCut).join(' '),
    };
  }
  return {
    businessOverview: text,
    keyRiskFactors: '',
    recommendation: '',
  };
}

function normalizeNarrativePayload(result: any) {
  if (!result) return null;
  if (result.narrative && typeof result.narrative === 'object') {
    return {
      businessOverview: result.narrative.businessOverview ?? result.narrative.business_overview ?? '',
      keyRiskFactors: result.narrative.keyRiskFactors ?? result.narrative.key_risk_factors ?? '',
      recommendation: result.narrative.recommendation ?? '',
    };
  }
  return parseNarrativeText(result.narrative_text ?? result.narrative);
}

function normalizeSourceBundle(result: any) {
  const sourcePayload = result?.sources ?? result?.narrative_sources;
  if (!sourcePayload || typeof sourcePayload !== 'object') return null;
  return {
    similarCasesCount:
      sourcePayload.similarCasesCount
      ?? sourcePayload.similar_cases_count
      ?? 0,
    similarCases:
      sourcePayload.similarCases
      ?? sourcePayload.similar_cases
      ?? [],
    rbiGuidelineSections:
      sourcePayload.rbiGuidelineSections
      ?? sourcePayload.rbi_guideline_sections
      ?? [],
    rulesApplied:
      sourcePayload.rulesApplied
      ?? sourcePayload.rules_applied
      ?? [],
    guidelinesReferenced:
      sourcePayload.guidelinesReferenced
      ?? sourcePayload.guidelines_referenced
      ?? [],
  };
}

function toSimilarCasesPanelCases(similarCases: Array<any> | undefined) {
  return (similarCases ?? []).slice(0, 3).map((item, index) => ({
    id: `${item.gstin || 'case'}-${index}`,
    gstin: item.gstin ?? 'UNKNOWN',
    score: Number(item.score ?? 0),
    riskBand: item.riskBand ?? item.risk_band ?? item.riskBandLabel ?? 'Unknown',
    outcome: item.outcome ?? 'pending',
    similarityReason: item.summary ?? 'Similar historical business profile.',
  }));
}

function HistoricalPatternCard({
  pattern,
}: {
  pattern: { explanation: string; confidence: number; lift: number; record_count: number }
}) {
  return (
    <div
      className="msme-card"
      style={{
        background: 'linear-gradient(180deg, rgba(12, 18, 36, 0.96), rgba(9, 15, 29, 0.92))',
        borderLeft: '3px solid rgba(129, 140, 248, 0.95)',
      }}
    >
      <div
        style={{
          color: 'rgba(165, 180, 252, 0.92)',
          fontFamily: 'var(--mono)',
          fontSize: 11,
          letterSpacing: '0.12em',
          marginBottom: 12,
          textTransform: 'uppercase',
        }}
      >
        Historical Pattern
      </div>
      <div style={{ color: 'var(--text)', fontSize: '0.98rem', lineHeight: 1.7 }}>
        {pattern.explanation}
      </div>
      <div
        style={{
          color: 'var(--text-dim)',
          display: 'flex',
          flexWrap: 'wrap',
          fontFamily: 'var(--mono)',
          fontSize: 11,
          gap: 14,
          letterSpacing: '0.06em',
          marginTop: 14,
          textTransform: 'uppercase',
        }}
      >
        <span>{Math.round(pattern.confidence * 100)}% confidence</span>
        <span>{pattern.lift.toFixed(1)}x lift</span>
        <span>{pattern.record_count} cases</span>
      </div>
    </div>
  );
}

export const MSMEScoring: React.FC<MSMEScoringProps> = ({ showTopbar = true }) => {
  const [gstin, setGstin] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [simulation, setSimulation] = useState<any>(null);
  const [graphData, setGraphData] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [narrativeRegenerating, setNarrativeRegenerating] = useState(false);
  const [pinnedResult, setPinnedResult] = useState<any>(null);
  const [activeStep, setActiveStep] = useState(0);
  const [showGraph, setShowGraph] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [historicalPatterns, setHistoricalPatterns] = useState<Array<{ explanation: string; confidence: number; lift: number; record_count: number }>>([]);

  useEffect(() => {
    if (!loading) {
      setActiveStep(0);
      return;
    }

    setActiveStep(0);
    const timer = window.setInterval(() => {
      setActiveStep(prev => (prev < SCORING_STEPS.length - 1 ? prev + 1 : prev));
    }, 500);
    return () => window.clearInterval(timer);
  }, [loading]);

  const normalizedGstin = useMemo(() => normalizeGstin(gstin), [gstin]);
  const validationError = useMemo(() => gstinValidationMessage(normalizedGstin), [normalizedGstin]);

  const freshnessMeta = useMemo(() => {
    const pipelines = result?.data_sources?.pipelines || {};
    const entries = Object.values(pipelines) as Array<{ freshness: string }>;
    const statuses = entries.map((entry) => {
      const ageMinutes = Math.max(0, Math.round((Date.now() - new Date(entry.freshness).getTime()) / 60000));
      if (ageMinutes < 30) return 'green';
      if (ageMinutes <= 240) return 'amber';
      return 'red';
    });
    return {
      anyManualReview: statuses.includes('amber') || statuses.includes('red'),
      anyRed: statuses.includes('red'),
    };
  }, [result]);

  const narrativePayload = useMemo(() => normalizeNarrativePayload(result), [result]);
  const sourceBundle = useMemo(() => normalizeSourceBundle(result), [result]);
  const similarCases = useMemo(
    () => toSimilarCasesPanelCases(sourceBundle?.similarCases),
    [sourceBundle],
  );

  useEffect(() => {
    if (!result?.gstin) {
      setHistoricalPatterns([]);
      return;
    }

    let cancelled = false;
    setHistoricalPatterns(Array.isArray(result.historical_patterns) ? result.historical_patterns : []);

    const loadHistoricalPatterns = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/api/insights/rules/match?gstin=${encodeURIComponent(result.gstin)}`,
          { headers: buildHeaders() },
        );
        if (!response.ok) return;
        const payload = await response.json() as { rules?: Array<{ explanation: string; confidence: number; lift: number; record_count: number }> };
        if (!cancelled && Array.isArray(payload.rules)) {
          setHistoricalPatterns(payload.rules);
        }
      } catch (matchError) {
        console.warn('Historical pattern fetch failed', matchError);
      }
    };

    void loadHistoricalPatterns();
    return () => {
      cancelled = true;
    };
  }, [result?.gstin]);

  const loadScoreArtifacts = async (targetGstin: string, targetCompanyName: string) => {
    const scoreUrl = `${API_BASE}/api/v1/score/${encodeURIComponent(targetGstin)}${targetCompanyName ? `?company_name=${encodeURIComponent(targetCompanyName)}` : ''}`;
    const scoreResp = await fetch(scoreUrl, { method: 'POST', headers: buildHeaders() });

    if (!scoreResp.ok) {
      const body = await scoreResp.json().catch(() => ({}));
      throw new Error(body.detail || `API returned ${scoreResp.status}`);
    }

    const data = await scoreResp.json();

    const simulationUrl = `${API_BASE}/api/v1/score/${encodeURIComponent(targetGstin)}/simulate${targetCompanyName ? `?company_name=${encodeURIComponent(targetCompanyName)}` : ''}`;
    let simulationData = null;
    try {
      const simulationResp = await fetch(simulationUrl, { headers: buildHeaders() });
      if (simulationResp.ok) {
        simulationData = await simulationResp.json();
      }
    } catch (simulationError) {
      console.warn('Simulation fetch failed', simulationError);
    }

    const graphUrl = `${API_BASE}/api/v1/entity-graph/${encodeURIComponent(targetGstin)}`;
    let graphPayload = null;
    try {
      const graphResp = await fetch(graphUrl, { headers: buildHeaders() });
      if (graphResp.ok) {
        graphPayload = await graphResp.json();
      }
    } catch (graphError) {
      console.warn('Entity graph fetch failed', graphError);
    }

    return { data, simulationData, graphPayload };
  };

  const handleScore = async (gstinOverride?: string, companyNameOverride?: string) => {
    const targetGstin = normalizeGstin(gstinOverride || gstin);
    const targetError = gstinValidationMessage(targetGstin);
    const targetCompanyName = companyNameOverride ?? companyName;
    if (targetError) {
      setError(targetError);
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setSimulation(null);
    setGraphData(null);
    setShowGraph(false);
    setChatOpen(false);

    try {
      const { data, simulationData, graphPayload } = await loadScoreArtifacts(targetGstin, targetCompanyName);
      setResult(data);
      setSimulation(simulationData);
      setGraphData(graphPayload);

      if (gstinOverride) {
        setGstin(gstinOverride);
      }
      if (companyNameOverride !== undefined) {
        setCompanyName(companyNameOverride);
      } else if (gstinOverride) {
        const demo = DEMO_GSTINS.find(d => d.gstin === gstinOverride);
        if (demo) setCompanyName(demo.company);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to connect to scoring API');
    } finally {
      setLoading(false);
    }
  };

  const handleNarrativeRegenerate = async () => {
    if (!result?.gstin) return;

    setNarrativeRegenerating(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/narrative`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify({
          gstin: result.gstin,
          company_name: companyName || undefined,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Narrative refresh failed with ${response.status}`);
      }
      const payload = await response.json();
      setResult((current: any) => ({
        ...current,
        narrative: payload.narrative,
        narrative_text: payload.narrative_text,
        narrative_sources: payload.sources,
        sources: payload.sources,
        narrative_model_used: payload.model_used,
      }));
    } catch (e: any) {
      setError(e.message || 'Failed to refresh narrative');
    } finally {
      setNarrativeRegenerating(false);
    }
  };

  const handleChatSend = async ({
    message,
    sessionId,
    applicationId,
  }: {
    message: string;
    sessionId: string | null;
    applicationId: string;
  }) => {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: buildHeaders(),
      body: JSON.stringify({
        gstin: applicationId,
        message,
        session_id: sessionId,
        company_name: companyName || undefined,
      }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Chat failed with ${response.status}`);
    }

    const payload = await response.json();
    return {
      reply: payload.reply,
      sessionId: payload.sessionId ?? payload.session_id,
      sources: payload.sources,
    };
  };

  const handleReset = () => {
    setResult(null);
    setError(null);
    setGstin('');
    setCompanyName('');
    setSimulation(null);
    setGraphData(null);
    setShowGraph(false);
    setChatOpen(false);
  };

  const handleRefresh = async (stream?: string) => {
    if (!result?.gstin) return;
    setRefreshing(true);
    try {
      const path = stream
        ? `/api/v1/score/${encodeURIComponent(result.gstin)}/refresh/${encodeURIComponent(stream)}`
        : `/api/v1/score/${encodeURIComponent(result.gstin)}/refresh`;
      const url = `${API_BASE}${path}${companyName ? `?company_name=${encodeURIComponent(companyName)}` : ''}`;
      const resp = await fetch(url, { method: 'POST', headers: buildHeaders() });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `Refresh failed with ${resp.status}`);
      }
      await handleScore(result.gstin);
    } catch (e: any) {
      setError(e.message || 'Failed to refresh data');
    } finally {
      setRefreshing(false);
    }
  };

  const handleExport = () => {
    if (!result?.gstin) return;
    const base = `${API_BASE}/api/v1/score/${encodeURIComponent(result.gstin)}/export.docx`;
    const url = withAuthQuery(companyName ? `${base}?company_name=${encodeURIComponent(companyName)}` : base);
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const content = (
    <div className={`msme-container ${chatOpen ? 'msme-container--chat-open' : ''}`}>
        <RuntimeStatusBanner apiBase={API_BASE} apiToken={API_TOKEN} />
        {/* Search card */}
        <div className="msme-card">
          <div className="msme-card-title">GSTIN Lookup</div>
          <div className="msme-search-wrap">
            <div className="msme-search-field">
              <label>GSTIN</label>
              <input
                className="msme-input"
                type="text"
                value={normalizedGstin}
                onChange={e => setGstin(normalizeGstin(e.target.value))}
                placeholder="e.g. 29AABCT1332Q1ZV"
                onKeyDown={e => e.key === 'Enter' && handleScore()}
              />
            </div>
            <div className="msme-search-field-sm">
              <label>Company Name (optional)</label>
              <input
                className="msme-input"
                type="text"
                value={companyName}
                onChange={e => setCompanyName(e.target.value)}
                placeholder="e.g. ABC Manufacturing"
              />
            </div>
            <button className="msme-btn" onClick={() => handleScore()} disabled={loading}>
              {loading ? <Loader2 size={14} className="msme-spin" /> : <Search size={14} />}
              {loading ? 'Scoring...' : 'Execute'}
            </button>
            {result && (
              <>
                <button className="msme-btn msme-btn--ghost" onClick={() => setPinnedResult(result)}>
                  Pin for Compare
                </button>
                <button className="msme-btn msme-btn--ghost" onClick={handleExport}>
                  <Download size={14} /> Export DOCX
                </button>
                <button className="msme-btn msme-btn--ghost" onClick={handleReset}>
                  <RotateCcw size={14} /> Reset
                </button>
              </>
            )}
          </div>
          {normalizedGstin && validationError && (
            <div className="msme-alert msme-alert--danger" style={{ marginTop: 12 }}>
              {validationError}
            </div>
          )}

          <div className="msme-demo-pills">
            <span className="msme-demo-label">Demo scenarios</span>
            {DEMO_GSTINS.map(d => (
              <button
                key={d.gstin}
                className="msme-demo-btn"
                onClick={() => { setGstin(d.gstin); setCompanyName(d.company); handleScore(d.gstin, d.company); }}
                disabled={loading}
              >
                {d.label} <code>{d.gstin.slice(0, 8)}...</code>
              </button>
            ))}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="msme-alert msme-alert--danger" style={{ marginBottom: 20 }}>
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <ScoringProgress steps={SCORING_STEPS} activeIndex={activeStep} />
            <div className="msme-card" style={{ textAlign: 'center', padding: '40px 20px' }}>
              <Loader2 size={32} className="msme-spin" color="var(--gold)" />
              <div style={{ marginTop: 16, fontFamily: 'var(--mono)', fontSize: '11px', color: 'var(--text-dim)', letterSpacing: '1px', textTransform: 'uppercase' as const }}>
                {SCORING_STEPS[activeStep]}
              </div>
              <div className="msme-skeleton-grid" style={{ marginTop: 24 }}>
                <div className="msme-skeleton-card" />
                <div className="msme-skeleton-card" />
                <div className="msme-skeleton-card" />
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {result && !loading && (
          <div className="msme-fadein" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <DataSourceBanner dataSources={result.data_sources} onRefresh={handleRefresh} refreshing={refreshing} />
            <ScoreHero
              creditScore={result.credit_score}
              riskBand={result.risk_band}
              percentile={result.percentile}
              scoreFreshness={result.score_freshness}
              fraudPenaltyApplied={result.fraud_penalty_applied}
              dataSparse={result.data_sparse}
              companyName={result.company_name}
              gstin={result.gstin}
              modelVersion={result.model_version}
              topReason={result.top_reasons?.[0] || null}
            />

            <NarrativeSummary
              isLoading={loading}
              narrative={narrativePayload}
              sources={sourceBundle}
              onRegenerate={handleNarrativeRegenerate}
              isRegenerating={narrativeRegenerating}
            />

            <SimilarCasesPanel cases={similarCases} isLoading={loading} />

            {historicalPatterns.length > 0 ? (
              <HistoricalPatternCard pattern={historicalPatterns[0]} />
            ) : null}

            {pinnedResult && pinnedResult.gstin !== result.gstin && (
              <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Comparison Mode</div><div className="msme-inline-meta">Loading comparison...</div></div>}>
                <ComparisonPanel pinned={pinnedResult} current={result} />
              </Suspense>
            )}

            <div className="msme-grid-2">
              {result.data_sparse ? (
                <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Manual Review Checklist</div><div className="msme-inline-meta">Loading checklist...</div></div>}>
                  <SparseDataChecklist signals={result.pipeline_signals} />
                </Suspense>
              ) : (
                <LoanRecommendation
                  recommendation={result.recommendation}
                  manualReviewRequired={freshnessMeta.anyManualReview}
                  manualReviewReason="One or more input streams are stale, so manual review is required before auto-approval."
                />
              )}
              <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Score Trend</div><div className="msme-inline-meta">Loading chart...</div></div>}>
                <ScoreTrend history={result.score_history} />
              </Suspense>
            </div>

            {simulation && (
              <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Score Improvement Simulator</div><div className="msme-inline-meta">Loading projection...</div></div>}>
                <ScoreImprovementSimulator simulation={simulation} />
              </Suspense>
            )}

            <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Audit Trail</div><div className="msme-inline-meta">Loading decision trace...</div></div>}>
              <AuditTrailPanel entries={result.audit_trail || []} />
            </Suspense>

            <div className="msme-grid-2">
              <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Decision Confidence</div><div className="msme-inline-meta">Loading panel...</div></div>}>
                <ConfidencePanel confidence={result.confidence_summary} />
              </Suspense>
              <ModelMetricsPanel
                modelVersion={result.model_version}
                metrics={result.model_metrics}
                backend={result.model_backend}
              />
            </div>

            <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Raw Feature Vector</div><div className="msme-inline-meta">Loading table...</div></div>}>
              <FeatureVectorTable featureVector={result.feature_vector} />
            </Suspense>

            <div>
              <div className="msme-section-title">Pipeline Signals</div>
              <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Pipeline Signals</div><div className="msme-inline-meta">Loading signals...</div></div>}>
                <PipelineSignals signals={result.pipeline_signals} />
              </Suspense>
            </div>

            <Suspense fallback={<div className="msme-card"><div className="msme-card-title">SHAP Waterfall</div><div className="msme-inline-meta">Loading attribution...</div></div>}>
              <ShapWaterfall
                baseScore={result.base_score}
                finalScore={result.credit_score}
                topReasons={result.top_reasons || []}
                waterfall={result.shap_waterfall || []}
              />
            </Suspense>

            <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Fraud Detection</div><div className="msme-inline-meta">Loading graph...</div></div>}>
              <FraudDetection fraud={result.fraud_detection} graphData={graphData} />
            </Suspense>

            {!showGraph && graphData && (
              <button
                className="msme-btn"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => setShowGraph(true)}
              >
                Show why - view fraud entity network
              </button>
            )}

            {showGraph && graphData && (
              <Suspense fallback={<div className="msme-card"><div className="msme-card-title">Entity Network Graph</div><div className="msme-inline-meta">Loading interactive graph...</div></div>}>
                <EntityGraph
                  gstin={result.gstin}
                  graphData={graphData}
                  fraudScore={result.fraud_detection?.risk_score ?? 0}
                  fraudExplanation={result.fraud_explanation}
                />
              </Suspense>
            )}
          </div>
        )}

        {/* Empty state */}
        {!result && !loading && !error && (
          <div className="msme-empty">
            <Search size={40} color="var(--text-dim)" style={{ opacity: 0.2 }} />
            <div className="msme-empty-title">Enter a GSTIN to begin assessment</div>
            <div className="msme-empty-sub">Use a valid 15-character GSTIN or select a demo scenario above</div>
          </div>
        )}

        {result ? (
          <ChatPanel
            applicationId={result.gstin}
            applicantName={result.company_name || companyName || result.gstin}
            creditScore={result.credit_score}
            onSendMessage={handleChatSend}
            isOpen={chatOpen}
            onToggle={() => setChatOpen((current) => !current)}
          />
        ) : null}
    </div>
  );

  if (!showTopbar) {
    return content;
  }

  return (
    <div className="msme-app">
      <div className="msme-topbar">
        <div className="msme-wordmark">INTELLI-CREDIT <span>MSME Scoring Engine</span></div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: '9px', color: 'var(--text-dim)', letterSpacing: '1.5px', opacity: 0.6 }}>
          v1.0 — REAL-TIME ASSESSMENT
        </div>
      </div>
      {content}
    </div>
  );
};
