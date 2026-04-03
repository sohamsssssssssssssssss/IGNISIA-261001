import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Hourglass,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import RuleCard from '../components/insights/RuleCard';
import RuleFilter from '../components/insights/RuleFilter';
import type { AssociationRule, FilterState } from '../types/insights';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';

interface InsightsPageProps {
  onNavigateToScoring?: () => void
}

interface ParsedInsightsPayload {
  rules: AssociationRule[]
  assessmentCount: number
  requiredAssessments: number
  lastUpdated: string | null
  notEnoughData: boolean
}

const DEFAULT_FILTERS: FilterState = {
  consequent: 'all',
  sortBy: 'confidence',
  minConfidence: 0.6,
};

const INSIGHTS_STYLES = `
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500;600&family=DM+Sans:ital,wght@0,400;0,500;1,400&family=Sora:wght@600;700&display=swap');

.insights-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.insights-page__header {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.insights-page__title {
  color: #f8fafc;
  font-family: 'Sora', sans-serif;
  font-size: clamp(1.8rem, 3vw, 2.5rem);
  font-weight: 700;
  letter-spacing: -0.04em;
}

.insights-page__subtitle {
  color: rgba(226, 232, 240, 0.72);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.98rem;
}

.insights-summary {
  color: rgba(226, 232, 240, 0.72);
  font-family: 'DM Mono', monospace;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.insights-rule-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.insights-error {
  align-items: center;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.22);
  border-radius: 14px;
  color: #fecaca;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  padding: 14px 16px;
}

.insights-error__copy {
  align-items: center;
  display: flex;
  gap: 10px;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.95rem;
}

.insights-button {
  align-items: center;
  background: transparent;
  border: 1px solid rgba(200, 168, 75, 0.35);
  border-radius: 999px;
  color: #f1d795;
  cursor: pointer;
  display: inline-flex;
  font-family: 'DM Mono', monospace;
  font-size: 0.72rem;
  gap: 8px;
  letter-spacing: 0.08em;
  padding: 9px 14px;
  text-transform: uppercase;
  transition: transform 150ms ease, border-color 150ms ease, background-color 150ms ease;
}

.insights-button:hover {
  background: rgba(200, 168, 75, 0.08);
  border-color: rgba(200, 168, 75, 0.5);
  transform: translateY(-1px);
}

.insights-empty {
  align-items: center;
  background: linear-gradient(180deg, rgba(17, 16, 18, 0.98), rgba(17, 16, 18, 0.9));
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 10px;
  padding: 40px 24px;
  text-align: center;
}

.insights-empty__icon {
  align-items: center;
  background: rgba(129, 140, 248, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.22);
  border-radius: 18px;
  color: #a5b4fc;
  display: inline-flex;
  height: 56px;
  justify-content: center;
  width: 56px;
}

.insights-empty__title {
  color: #f8fafc;
  font-family: 'Sora', sans-serif;
  font-size: 1.2rem;
  font-weight: 600;
  line-height: 1.35;
  max-width: 620px;
}

.insights-empty__body {
  color: rgba(226, 232, 240, 0.7);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.95rem;
  line-height: 1.65;
  max-width: 620px;
}

.insights-filter {
  background: rgba(17, 16, 18, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
}

.insights-filter__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

.insights-filter__group {
  display: flex;
  flex: 1 1 240px;
  flex-direction: column;
  gap: 8px;
}

.insights-filter__group--compact {
  flex: 0 1 180px;
}

.insights-filter__group--slider {
  flex: 1 1 220px;
}

.insights-filter__label {
  color: rgba(226, 232, 240, 0.65);
  font-family: 'DM Mono', monospace;
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.insights-segmented {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px;
}

.insights-segmented__item {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  color: rgba(226, 232, 240, 0.72);
  cursor: pointer;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.84rem;
  padding: 8px 12px;
  transition: all 150ms ease;
}

.insights-segmented__item--positive.is-active {
  background: rgba(16, 185, 129, 0.14);
  border-color: rgba(16, 185, 129, 0.36);
  color: #86efac;
}

.insights-segmented__item--negative.is-active {
  background: rgba(239, 68, 68, 0.14);
  border-color: rgba(239, 68, 68, 0.36);
  color: #fda4af;
}

.insights-segmented__item--neutral.is-active {
  background: rgba(59, 130, 246, 0.14);
  border-color: rgba(59, 130, 246, 0.36);
  color: #93c5fd;
}

.insights-select,
.insights-slider {
  width: 100%;
}

.insights-select {
  appearance: none;
  background: rgba(8, 7, 9, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  color: #f8fafc;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.92rem;
  padding: 10px 12px;
}

.insights-slider {
  accent-color: #c8a84b;
}

.insights-filter__meta {
  color: rgba(226, 232, 240, 0.55);
  font-family: 'DM Sans', sans-serif;
  font-size: 0.82rem;
}

.insights-filter__chips {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.insights-filter-chip,
.insights-filter__clear {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  color: rgba(226, 232, 240, 0.8);
  cursor: pointer;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.82rem;
  padding: 6px 10px;
}

.insights-filter-chip {
  align-items: center;
  display: inline-flex;
  gap: 8px;
}

.insights-filter__clear {
  border: none;
  color: #f1d795;
  padding-left: 0;
}

.insights-rule-card {
  background: rgba(17, 16, 18, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-left: 3px solid transparent;
  border-radius: 18px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12);
  padding: 18px 18px 16px;
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.insights-rule-card:hover {
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.16);
  transform: translateY(-2px);
}

.insights-rule-card--positive {
  border-left-color: #22c55e;
}

.insights-rule-card--negative {
  border-left-color: #ef4444;
}

.insights-rule-card__badge-row {
  display: flex;
  margin-bottom: 14px;
}

.insights-outcome-badge {
  align-items: center;
  border-radius: 999px;
  display: inline-flex;
  font-family: 'DM Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  gap: 8px;
  letter-spacing: 0.08em;
  padding: 7px 12px;
  text-transform: uppercase;
}

.insights-outcome-badge__dot {
  border-radius: 999px;
  display: inline-block;
  height: 7px;
  width: 7px;
}

.insights-outcome-badge--positive {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.25);
  color: #86efac;
}

.insights-outcome-badge--positive .insights-outcome-badge__dot {
  background: #22c55e;
}

.insights-outcome-badge--negative {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #fda4af;
}

.insights-outcome-badge--negative .insights-outcome-badge__dot {
  background: #ef4444;
}

.insights-rule-card__explanation {
  color: #f8fafc;
  font-family: 'DM Sans', sans-serif;
  font-size: clamp(1rem, 1.3vw, 1.08rem);
  line-height: 1.7;
  margin: 0;
}

.insights-rule-card__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.insights-metric {
  align-items: center;
  border-radius: 999px;
  cursor: default;
  display: inline-flex;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.82rem;
  gap: 8px;
  padding: 8px 11px;
  position: relative;
}

.insights-metric__icon {
  display: inline-flex;
}

.insights-metric--neutral {
  background: rgba(59, 130, 246, 0.12);
  color: #bfdbfe;
}

.insights-metric--positive {
  background: rgba(34, 197, 94, 0.14);
  color: #86efac;
}

.insights-metric--warning {
  background: rgba(245, 158, 11, 0.14);
  color: #fcd34d;
}

.insights-metric--muted {
  background: rgba(249, 115, 22, 0.14);
  color: #fdba74;
}

.insights-metric--elevated {
  background: rgba(168, 85, 247, 0.14);
  color: #d8b4fe;
}

.insights-tooltip {
  background: #0d0c0e;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.2);
  color: #e2e8f0;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.78rem;
  line-height: 1.45;
  max-width: 220px;
  opacity: 0;
  padding: 8px 10px;
  pointer-events: none;
  position: absolute;
  top: calc(100% + 10px);
  left: 0;
  transform: translateY(4px);
  transition: opacity 150ms ease, transform 150ms ease;
  z-index: 5;
}

.insights-metric:hover .insights-tooltip {
  opacity: 1;
  transform: translateY(0);
}

.insights-rule-card__toggle {
  align-items: center;
  background: transparent;
  border: none;
  color: #f1d795;
  cursor: pointer;
  display: inline-flex;
  font-family: 'DM Mono', monospace;
  font-size: 0.74rem;
  gap: 8px;
  letter-spacing: 0.08em;
  margin-top: 16px;
  text-transform: uppercase;
}

.insights-rule-card__accordion {
  overflow: hidden;
  transition: max-height 200ms ease-in-out;
}

.insights-rule-card__accordion-inner {
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
  padding-top: 14px;
}

.insights-rule-card__section-title {
  color: rgba(226, 232, 240, 0.6);
  font-family: 'DM Mono', monospace;
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.insights-rule-card__antecedents {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insights-rule-card__antecedent {
  align-items: center;
  color: #dbe4f0;
  display: flex;
  font-family: 'DM Sans', sans-serif;
  gap: 10px;
}

.insights-rule-card__antecedent svg {
  color: #22c55e;
}

.insights-rule-card__outcome {
  font-family: 'DM Sans', sans-serif;
  font-size: 0.95rem;
  text-transform: capitalize;
}

.insights-rule-card__outcome--positive {
  color: #86efac;
}

.insights-rule-card__outcome--negative {
  color: #fda4af;
}

.insights-rule-card__profile {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
}

.insights-rule-card__profile-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.insights-rule-card__profile-head {
  color: #dbe4f0;
  display: flex;
  font-family: 'DM Sans', sans-serif;
  font-size: 0.84rem;
  justify-content: space-between;
  gap: 12px;
}

.insights-rule-card__profile-track {
  background: rgba(148, 163, 184, 0.18);
  border-radius: 999px;
  height: 8px;
  overflow: hidden;
}

.insights-rule-card__profile-fill {
  background: linear-gradient(90deg, #60a5fa 0%, #c8a84b 100%);
  border-radius: 999px;
  height: 100%;
}

.insights-rule-card__profile-empty {
  align-items: center;
  color: rgba(226, 232, 240, 0.6);
  display: flex;
  font-family: 'DM Sans', sans-serif;
  gap: 8px;
}

.insights-skeleton {
  animation: insights-shimmer 1.5s linear infinite;
  background: linear-gradient(
    90deg,
    rgba(255,255,255,0.05) 25%,
    rgba(255,255,255,0.12) 50%,
    rgba(255,255,255,0.05) 75%
  );
  background-size: 800px 100%;
  border-radius: 12px;
}

.insights-skeleton-card {
  background: rgba(17, 16, 18, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-left: 3px solid rgba(200, 168, 75, 0.25);
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
}

.insights-skeleton-pill {
  height: 30px;
  width: 150px;
}

.insights-skeleton-line-lg {
  height: 18px;
  width: 88%;
}

.insights-skeleton-line-md {
  height: 14px;
  width: 94%;
}

.insights-skeleton-line-sm {
  height: 14px;
  width: 64%;
}

.insights-skeleton-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.insights-skeleton-badge {
  height: 34px;
  width: 132px;
}

@keyframes insights-shimmer {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}

@media (max-width: 900px) {
  .insights-filter__controls {
    flex-direction: column;
  }

  .insights-rule-card__metrics {
    flex-direction: column;
  }

  .insights-summary {
    line-height: 1.6;
  }
}
`;

function isAssociationRule(value: unknown): value is AssociationRule {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return Array.isArray(candidate.antecedents)
    && (candidate.consequent === 'repaid' || candidate.consequent === 'defaulted')
    && typeof candidate.support === 'number'
    && typeof candidate.confidence === 'number'
    && typeof candidate.lift === 'number'
    && typeof candidate.explanation === 'string';
}

function parseInsightsPayload(raw: unknown): ParsedInsightsPayload {
  if (Array.isArray(raw)) {
    const rules = raw.filter(isAssociationRule);
    return {
      rules,
      assessmentCount: 0,
      requiredAssessments: 50,
      lastUpdated: new Date().toISOString(),
      notEnoughData: rules.length === 0,
    };
  }

  if (typeof raw !== 'object' || raw === null) {
    return {
      rules: [],
      assessmentCount: 0,
      requiredAssessments: 50,
      lastUpdated: null,
      notEnoughData: true,
    };
  }

  const payload = raw as Record<string, unknown>;
  const rules = (Array.isArray(payload.rules) ? payload.rules : Array.isArray(payload.items) ? payload.items : [])
    .filter(isAssociationRule);

  const assessmentCount = typeof payload.assessmentCount === 'number'
    ? payload.assessmentCount
    : typeof payload.assessment_count === 'number'
      ? payload.assessment_count
      : typeof payload.currentAssessments === 'number'
        ? payload.currentAssessments
        : typeof payload.current_assessments === 'number'
          ? payload.current_assessments
          : 0;

  const requiredAssessments = typeof payload.requiredAssessments === 'number'
    ? payload.requiredAssessments
    : typeof payload.required_assessments === 'number'
      ? payload.required_assessments
      : typeof payload.minimumAssessments === 'number'
        ? payload.minimumAssessments
        : typeof payload.minimum_assessments === 'number'
          ? payload.minimum_assessments
          : 50;

  const lastUpdated = typeof payload.lastUpdated === 'string'
    ? payload.lastUpdated
    : typeof payload.last_updated === 'string'
      ? payload.last_updated
      : typeof payload.generatedAt === 'string'
        ? payload.generatedAt
        : typeof payload.generated_at === 'string'
          ? payload.generated_at
          : rules.length > 0
            ? new Date().toISOString()
            : null;

  const notEnoughData = payload.notEnoughData === true
    || payload.not_enough_data === true
    || (rules.length === 0 && assessmentCount < requiredAssessments);

  return {
    rules,
    assessmentCount,
    requiredAssessments,
    lastUpdated,
    notEnoughData,
  };
}

function SkeletonList() {
  return (
    <div className="insights-rule-list">
      {[0, 1, 2].map((index) => (
        <div key={index} className="insights-skeleton-card">
          <div className="insights-skeleton insights-skeleton-pill" />
          <div className="insights-skeleton insights-skeleton-line-lg" />
          <div className="insights-skeleton insights-skeleton-line-md" />
          <div className="insights-skeleton insights-skeleton-line-sm" />
          <div className="insights-skeleton-badges">
            <div className="insights-skeleton insights-skeleton-badge" />
            <div className="insights-skeleton insights-skeleton-badge" />
            <div className="insights-skeleton insights-skeleton-badge" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function InsightsPage({ onNavigateToScoring }: InsightsPageProps) {
  const [rules, setRules] = useState<AssociationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [assessmentCount, setAssessmentCount] = useState(0);
  const [requiredAssessments, setRequiredAssessments] = useState(50);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [notEnoughData, setNotEnoughData] = useState(false);

  const loadRules = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/insights/rules`, {
        headers: API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : undefined,
      });
      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }

      const raw = await response.json() as unknown;
      const parsed = parseInsightsPayload(raw);
      setRules(parsed.rules);
      setAssessmentCount(parsed.assessmentCount);
      setRequiredAssessments(parsed.requiredAssessments);
      setLastUpdated(parsed.lastUpdated);
      setNotEnoughData(parsed.notEnoughData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load patterns.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRules();
  }, [loadRules]);

  const filteredRules = useMemo(() => {
    const sorted = [...rules]
      .filter((rule) => (filters.consequent === 'all' ? true : rule.consequent === filters.consequent))
      .filter((rule) => rule.confidence >= filters.minConfidence)
      .sort((left, right) => right[filters.sortBy] - left[filters.sortBy]);

    return sorted;
  }, [filters, rules]);

  const handleNavigateToScoring = () => {
    if (onNavigateToScoring) {
      onNavigateToScoring();
      return;
    }
    window.history.pushState({}, '', '/');
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const remainingAssessments = Math.max(requiredAssessments - assessmentCount, 0);
  const summaryTimestamp = lastUpdated
    ? new Date(lastUpdated).toLocaleString([], {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
    : 'Unavailable';

  return (
    <div className="msme-container">
      <style>{INSIGHTS_STYLES}</style>
      <section className="insights-page">
        <header className="insights-page__header">
          <h1 className="insights-page__title">Behavioral Patterns</h1>
          <p className="insights-page__subtitle">Discovered from your assessment history</p>
        </header>

        {loading ? (
          <SkeletonList />
        ) : error ? (
          <div className="insights-error">
            <div className="insights-error__copy">
              <AlertTriangle size={18} />
              <span>Could not load patterns. Retry?</span>
            </div>
            <button type="button" className="insights-button" onClick={() => void loadRules()}>
              <RefreshCw size={14} />
              Retry
            </button>
          </div>
        ) : rules.length === 0 || notEnoughData ? (
          <div className="insights-empty">
            <div className="insights-empty__icon">
              <Hourglass size={26} />
            </div>
            <div className="insights-empty__title">
              Patterns will appear here after 50 businesses have been assessed
            </div>
            <div className="insights-empty__body">
              Currently {assessmentCount} assessments completed. {remainingAssessments} more needed.
            </div>
            <button type="button" className="insights-button" onClick={handleNavigateToScoring}>
              <Sparkles size={14} />
              Run an Assessment
            </button>
          </div>
        ) : (
          <>
            <RuleFilter
              totalCount={rules.length}
              filteredCount={filteredRules.length}
              onFilterChange={setFilters}
            />

            <div className="insights-summary">
              Showing {filteredRules.length} of {rules.length} patterns · Last updated {summaryTimestamp}
            </div>

            {filteredRules.length > 0 ? (
              <div className="insights-rule-list">
                {filteredRules.map((rule, index) => (
                  <div key={`${rule.consequent}-${rule.antecedents.join('-')}-${index}`}>
                    <RuleCard {...rule} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="insights-empty">
                <div className="insights-empty__icon">
                  <TrendingUp size={26} />
                </div>
                <div className="insights-empty__title">No patterns match the current filters</div>
                <div className="insights-empty__body">
                  Relax a filter or lower the minimum confidence threshold to reveal more rules.
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
