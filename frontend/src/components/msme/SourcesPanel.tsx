import React, { useEffect, useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileText,
  Paperclip,
} from 'lucide-react';
import type {
  AppliedRule,
  GuidelineReference,
  SimilarCase,
  SourcesPanelProps,
} from '../../types/sources';

interface RenderableSimilarCase extends SimilarCase {
  summary?: string;
}

function buildCountLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

function maskGstin(gstin: string, privacyMode: boolean): string {
  if (!privacyMode) return gstin;
  if (gstin.length <= 9) return `${gstin.slice(0, 5)}****`;
  return `${gstin.slice(0, 5)}****${gstin.slice(-4)}`;
}

function formatOutcome(outcome: SimilarCase['outcome']): string {
  if (outcome === 'repaid') return 'Repaid';
  if (outcome === 'defaulted') return 'Defaulted';
  return 'Pending';
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function navigateTo(pathname: string) {
  window.history.pushState({}, '', pathname);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function isExternalGuideline(reference: GuidelineReference): boolean {
  return typeof reference.url === 'string' && reference.url.trim().length > 0;
}

function RuleRow({ rule }: { rule: AppliedRule }) {
  return (
    <div className="sp-row sp-rule-row" tabIndex={0}>
      <div className="sp-rule-line">
        {rule.antecedents.join(' + ')} <span className="sp-rule-arrow">→</span>{' '}
        <span className={rule.consequent === 'repaid' ? 'sp-rule-positive' : 'sp-rule-negative'}>
          {rule.consequent}
        </span>
      </div>
      <div className="sp-rule-meta">
        Confidence: {formatPercent(rule.confidence)} · Support: {formatPercent(rule.support)}
      </div>
      <span className="sp-tooltip" role="tooltip">
        {rule.explanation}
      </span>
    </div>
  );
}

export default function SourcesPanel({
  similarCases,
  rulesApplied,
  guidelinesReferenced,
  defaultExpanded = false,
  privacyMode = false,
}: SourcesPanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [isCasesExpanded, setIsCasesExpanded] = useState(defaultExpanded);
  const [isRulesExpanded, setIsRulesExpanded] = useState(defaultExpanded);
  const [isGuidelinesExpanded, setIsGuidelinesExpanded] = useState(defaultExpanded);
  const [expandedGuidelines, setExpandedGuidelines] = useState<Set<string>>(new Set());
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const hasSimilarCases = similarCases.length > 0;
  const hasRules = rulesApplied.length > 0;
  const hasGuidelines = guidelinesReferenced.length > 0;
  const hasContent = hasSimilarCases || hasRules || hasGuidelines;

  const countSummary = useMemo(() => {
    const parts: string[] = [];
    if (hasSimilarCases) parts.push(buildCountLabel(similarCases.length, 'similar case', 'similar cases'));
    if (hasRules) parts.push(buildCountLabel(rulesApplied.length, 'rule', 'rules'));
    if (hasGuidelines) parts.push(buildCountLabel(guidelinesReferenced.length, 'guideline', 'guidelines'));
    return parts.join(' · ');
  }, [
    guidelinesReferenced.length,
    hasGuidelines,
    hasRules,
    hasSimilarCases,
    rulesApplied.length,
    similarCases.length,
  ]);

  useEffect(() => {
    setIsExpanded(defaultExpanded);
    setIsCasesExpanded(defaultExpanded);
    setIsRulesExpanded(defaultExpanded);
    setIsGuidelinesExpanded(defaultExpanded);
  }, [defaultExpanded]);

  useEffect(() => {
    if (!toastMessage) return undefined;

    const timeout = window.setTimeout(() => setToastMessage(null), 2400);
    return () => window.clearTimeout(timeout);
  }, [toastMessage]);

  if (!hasContent) {
    return null;
  }

  const handlePanelToggle = () => {
    setIsExpanded((current) => {
      const next = !current;
      if (next) {
        if (hasSimilarCases) setIsCasesExpanded(true);
        if (hasRules) setIsRulesExpanded(true);
        if (hasGuidelines) setIsGuidelinesExpanded(true);
      }
      return next;
    });
  };

  const toggleGuidelineInline = (key: string) => {
    setExpandedGuidelines((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  return (
    <>
      <style>{SOURCES_PANEL_CSS}</style>
      <div className="sp-root">
        <button type="button" className="sp-header" onClick={handlePanelToggle}>
          <span className="sp-header-left">
            <Paperclip size={14} />
            <span className="sp-header-title">
              Sources used in this analysis
              <span className="sp-header-summary">({countSummary})</span>
            </span>
          </span>
          <ChevronRight
            size={16}
            className={`sp-chevron ${isExpanded ? 'sp-chevron-open' : ''}`}
          />
        </button>

        <div className={`sp-body ${isExpanded ? 'sp-body-open' : ''}`}>
          {hasSimilarCases ? (
            <section className="sp-section">
              <button
                type="button"
                className="sp-section-toggle"
                onClick={() => setIsCasesExpanded((current) => !current)}
              >
                <span>SIMILAR CASES ({similarCases.length})</span>
                {isCasesExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>

              <div className={`sp-section-body ${isCasesExpanded ? 'sp-section-body-open' : ''}`}>
                {similarCases.map((item, index) => {
                  const similarCase = item as RenderableSimilarCase;
                  const gstin = maskGstin(similarCase.gstin, privacyMode);
                  const similarityLabel = typeof similarCase.similarityScore === 'number'
                    ? `${Math.round(similarCase.similarityScore * 100)}% similar`
                    : null;
                  const hasScore = Number.isFinite(similarCase.score) && similarCase.score > 0;

                  return (
                    <button
                      key={`${similarCase.gstin}-${index}`}
                      type="button"
                      className="sp-row sp-case-row"
                      onClick={() => {
                        if (similarCase.existsInHistory) {
                          navigateTo(`/score-history/${encodeURIComponent(similarCase.gstin)}`);
                          return;
                        }
                        setToastMessage('Full record not available');
                      }}
                    >
                      <div className="sp-case-main">
                        <div className="sp-case-topline">
                          <span className="sp-case-gstin">{gstin}</span>
                          {similarityLabel ? <span className="sp-case-similarity">{similarityLabel}</span> : null}
                        </div>
                        {similarCase.summary ? (
                          <div className="sp-case-summary">{similarCase.summary}</div>
                        ) : null}
                      </div>

                      <div className="sp-case-side">
                        {hasScore ? <span className="sp-score-badge">Score: {similarCase.score}</span> : null}
                        <span className={`sp-outcome-pill sp-outcome-${similarCase.outcome}`}>
                          <span className="sp-outcome-dot" />
                          {formatOutcome(similarCase.outcome)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>
          ) : null}

          {hasRules ? (
            <section className="sp-section">
              <button
                type="button"
                className="sp-section-toggle"
                onClick={() => setIsRulesExpanded((current) => !current)}
              >
                <span>RULES APPLIED ({rulesApplied.length})</span>
                {isRulesExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>

              <div className={`sp-section-body ${isRulesExpanded ? 'sp-section-body-open' : ''}`}>
                {rulesApplied.map((rule, index) => (
                  <RuleRow key={`${rule.antecedents.join('+')}-${rule.consequent}-${index}`} rule={rule} />
                ))}
              </div>
            </section>
          ) : null}

          {hasGuidelines ? (
            <section className="sp-section">
              <button
                type="button"
                className="sp-section-toggle"
                onClick={() => setIsGuidelinesExpanded((current) => !current)}
              >
                <span>GUIDELINES REFERENCED ({guidelinesReferenced.length})</span>
                {isGuidelinesExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>

              <div className={`sp-section-body ${isGuidelinesExpanded ? 'sp-section-body-open' : ''}`}>
                {guidelinesReferenced.map((reference, index) => {
                  const guidelineKey = `${reference.title}-${reference.section}-${index}`;
                  const isExpandedInline = expandedGuidelines.has(guidelineKey);
                  const interactive = isExternalGuideline(reference);

                  if (interactive) {
                    return (
                      <a
                        key={guidelineKey}
                        className="sp-row sp-guideline-row"
                        href={reference.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <div className="sp-guideline-top">
                          <span className="sp-guideline-icon-wrap">
                            <FileText size={14} />
                          </span>
                          <span className="sp-guideline-title">{reference.title}</span>
                          <ExternalLink size={14} className="sp-guideline-action" />
                        </div>
                        <div className="sp-guideline-section">{reference.section}</div>
                        <div className="sp-guideline-excerpt sp-guideline-excerpt-clamped">
                          {reference.excerpt}
                        </div>
                      </a>
                    );
                  }

                  return (
                    <button
                      key={guidelineKey}
                      type="button"
                      className="sp-row sp-guideline-row"
                      onClick={() => toggleGuidelineInline(guidelineKey)}
                    >
                      <div className="sp-guideline-top">
                        <span className="sp-guideline-icon-wrap">
                          <FileText size={14} />
                        </span>
                        <span className="sp-guideline-title">{reference.title}</span>
                        <ChevronDown
                          size={14}
                          className={`sp-guideline-action ${isExpandedInline ? 'sp-chevron-open' : ''}`}
                        />
                      </div>
                      <div className="sp-guideline-section">{reference.section}</div>
                      <div
                        className={`sp-guideline-excerpt ${isExpandedInline ? '' : 'sp-guideline-excerpt-clamped'}`}
                      >
                        {reference.excerpt}
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>
          ) : null}
        </div>
      </div>

      {toastMessage ? (
        <div className="sp-toast" role="status" aria-live="polite">
          {toastMessage}
        </div>
      ) : null}
    </>
  );
}

const SOURCES_PANEL_CSS = `
.sp-root {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  overflow: hidden;
  color: #0f172a;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.sp-header,
.sp-section-toggle,
.sp-case-row,
.sp-guideline-row {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 0;
  color: inherit;
  font: inherit;
  text-align: left;
}

.sp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 160ms ease;
}

.sp-header:hover,
.sp-section-toggle:hover,
.sp-row:hover {
  background: rgba(255, 255, 255, 0.72);
}

.sp-header-left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: #475569;
}

.sp-header-title {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
  font-size: 0.88rem;
  font-weight: 600;
  color: #0f172a;
}

.sp-header-summary {
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 500;
}

.sp-chevron {
  color: #64748b;
  transition: transform 150ms ease;
}

.sp-chevron-open {
  transform: rotate(90deg);
}

.sp-body {
  max-height: 0;
  overflow: hidden;
  transition: max-height 200ms ease-in-out;
}

.sp-body-open {
  max-height: 2200px;
}

.sp-section + .sp-section {
  border-top: 1px solid #e2e8f0;
}

.sp-section-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px 8px;
  cursor: pointer;
  color: #64748b;
  font-family: 'DM Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sp-section-body {
  max-height: 0;
  overflow: hidden;
  transition: max-height 150ms ease-in-out;
}

.sp-section-body-open {
  max-height: 1400px;
}

.sp-row {
  display: block;
  padding: 10px 16px 12px;
  transition: background-color 150ms ease;
}

.sp-row + .sp-row {
  border-top: 1px solid rgba(226, 232, 240, 0.7);
}

.sp-case-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
}

.sp-case-main {
  min-width: 0;
  flex: 1;
}

.sp-case-topline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.sp-case-gstin {
  font-family: 'DM Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.78rem;
  font-weight: 600;
  color: #0f172a;
}

.sp-case-similarity {
  font-size: 0.72rem;
  color: #64748b;
}

.sp-case-summary {
  margin-top: 6px;
  color: #64748b;
  font-size: 0.78rem;
  line-height: 1.45;
}

.sp-case-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.sp-score-badge {
  border-radius: 999px;
  background: #e2e8f0;
  color: #334155;
  font-size: 0.7rem;
  padding: 4px 9px;
  white-space: nowrap;
}

.sp-outcome-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  font-size: 0.72rem;
  padding: 4px 10px;
  white-space: nowrap;
}

.sp-outcome-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 10px currentColor;
}

.sp-outcome-repaid {
  background: #dcfce7;
  color: #15803d;
}

.sp-outcome-defaulted {
  background: #fee2e2;
  color: #b91c1c;
}

.sp-outcome-pending {
  background: #e2e8f0;
  color: #64748b;
}

.sp-rule-row {
  position: relative;
  cursor: default;
}

.sp-rule-line {
  font-size: 0.84rem;
  line-height: 1.55;
  color: #0f172a;
}

.sp-rule-arrow {
  color: #475569;
}

.sp-rule-positive {
  color: #15803d;
  font-weight: 600;
}

.sp-rule-negative {
  color: #b91c1c;
  font-weight: 600;
}

.sp-rule-meta {
  margin-top: 4px;
  color: #64748b;
  font-size: 0.75rem;
}

.sp-tooltip {
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: calc(100% - 2px);
  z-index: 10;
  opacity: 0;
  pointer-events: none;
  transform: translateY(6px);
  transition: opacity 140ms ease, transform 140ms ease;
  background: #0f172a;
  color: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);
  font-size: 0.76rem;
  line-height: 1.5;
}

.sp-rule-row:hover .sp-tooltip,
.sp-rule-row:focus-within .sp-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.sp-guideline-row {
  cursor: pointer;
  text-decoration: none;
}

.sp-guideline-top {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0f172a;
}

.sp-guideline-icon-wrap {
  color: #64748b;
  display: inline-flex;
  align-items: center;
}

.sp-guideline-title {
  font-size: 0.84rem;
  font-weight: 600;
  flex: 1;
}

.sp-guideline-action {
  color: #64748b;
  flex-shrink: 0;
  transition: transform 150ms ease;
}

.sp-guideline-section {
  margin-top: 4px;
  color: #64748b;
  font-size: 0.75rem;
}

.sp-guideline-excerpt {
  margin-top: 8px;
  border-left: 2px solid #cbd5e1;
  background: rgba(255, 255, 255, 0.7);
  padding: 8px 0 8px 12px;
  color: #475569;
  font-size: 0.78rem;
  font-style: italic;
  line-height: 1.55;
}

.sp-guideline-excerpt-clamped {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.sp-toast {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 80;
  border-radius: 12px;
  background: #0f172a;
  color: #f8fafc;
  padding: 10px 14px;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.18);
  font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif;
  font-size: 0.82rem;
}

@media (max-width: 640px) {
  .sp-header,
  .sp-section-toggle,
  .sp-row {
    padding-left: 14px;
    padding-right: 14px;
  }

  .sp-case-row {
    flex-direction: column;
    align-items: stretch;
  }

  .sp-case-side {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
}
`;
