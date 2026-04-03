import React, { useEffect, useMemo, useState } from 'react';
import type { FilterState } from '../../types/insights';

interface RuleFilterProps {
  onFilterChange: (filters: FilterState) => void
  totalCount: number
  filteredCount: number
}

const DEFAULT_FILTERS: FilterState = {
  consequent: 'all',
  sortBy: 'confidence',
  minConfidence: 0.6,
};

export default function RuleFilter({
  onFilterChange,
  totalCount,
  filteredCount,
}: RuleFilterProps) {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  useEffect(() => {
    onFilterChange(filters);
  }, [filters, onFilterChange]);

  const activeChips = useMemo(() => {
    const chips: Array<{ key: keyof FilterState; label: string }> = [];
    if (filters.consequent !== 'all') {
      chips.push({
        key: 'consequent',
        label: filters.consequent === 'repaid' ? 'Repayment ↑' : 'Default ↓',
      });
    }
    if (filters.sortBy !== 'confidence') {
      chips.push({
        key: 'sortBy',
        label: `Sort: ${filters.sortBy[0].toUpperCase()}${filters.sortBy.slice(1)}`,
      });
    }
    if (filters.minConfidence !== DEFAULT_FILTERS.minConfidence) {
      chips.push({
        key: 'minConfidence',
        label: `Min. confidence: ${Math.round(filters.minConfidence * 100)}%`,
      });
    }
    return chips;
  }, [filters]);

  const resetChip = (key: keyof FilterState) => {
    setFilters((current) => ({
      ...current,
      [key]: DEFAULT_FILTERS[key],
    }));
  };

  return (
    <section className="insights-filter">
      <div className="insights-filter__controls">
        <div className="insights-filter__group">
          <span className="insights-filter__label">Pattern type</span>
          <div className="insights-segmented">
            {[
              { label: 'All Patterns', value: 'all' as const, tone: 'neutral' },
              { label: 'Repayment ↑', value: 'repaid' as const, tone: 'positive' },
              { label: 'Default ↓', value: 'defaulted' as const, tone: 'negative' },
            ].map((option) => (
              <button
                key={option.value}
                type="button"
                className={[
                  'insights-segmented__item',
                  `insights-segmented__item--${option.tone}`,
                  filters.consequent === option.value ? 'is-active' : '',
                ].join(' ').trim()}
                onClick={() => setFilters((current) => ({ ...current, consequent: option.value }))}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="insights-filter__group insights-filter__group--compact">
          <label className="insights-filter__label" htmlFor="insights-sort">
            Sort by:
          </label>
          <select
            id="insights-sort"
            className="insights-select"
            value={filters.sortBy}
            onChange={(event) => setFilters((current) => ({
              ...current,
              sortBy: event.target.value as FilterState['sortBy'],
            }))}
          >
            <option value="confidence">Confidence</option>
            <option value="support">Support</option>
            <option value="lift">Lift</option>
          </select>
        </div>

        <div className="insights-filter__group insights-filter__group--slider">
          <label className="insights-filter__label" htmlFor="insights-confidence">
            Min. confidence: {Math.round(filters.minConfidence * 100)}%
          </label>
          <input
            id="insights-confidence"
            className="insights-slider"
            type="range"
            min={60}
            max={100}
            step={5}
            value={Math.round(filters.minConfidence * 100)}
            onChange={(event) => setFilters((current) => ({
              ...current,
              minConfidence: Number(event.target.value) / 100,
            }))}
          />
        </div>
      </div>

      <div className="insights-filter__meta">
        <span>{filteredCount} of {totalCount} visible</span>
      </div>

      {activeChips.length > 0 ? (
        <div className="insights-filter__chips">
          {activeChips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              className="insights-filter-chip"
              onClick={() => resetChip(chip.key)}
            >
              {chip.label}
              <span aria-hidden="true">×</span>
            </button>
          ))}
          <button
            type="button"
            className="insights-filter__clear"
            onClick={() => setFilters(DEFAULT_FILTERS)}
          >
            Clear all filters
          </button>
        </div>
      ) : null}
    </section>
  );
}
