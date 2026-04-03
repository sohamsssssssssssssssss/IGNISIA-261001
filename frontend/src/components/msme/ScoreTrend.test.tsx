import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ScoreTrend } from './ScoreTrend';

describe('ScoreTrend', () => {
  it('renders legend labels and score history state', () => {
    render(
      <ScoreTrend
        history={[
          { timestamp: '2026-01-01T00:00:00Z', score: 640, risk_band: 'MODERATE_RISK', fraud_risk: 'LOW', source: 'api' },
          { timestamp: '2026-02-01T00:00:00Z', score: 702, risk_band: 'LOW_RISK', fraud_risk: 'LOW', source: 'api' },
        ]}
      />
    );

    expect(screen.getByText('Score Trend')).toBeInTheDocument();
    expect(screen.getByText('Very Low Risk')).toBeInTheDocument();
    expect(screen.getByText('Moderate')).toBeInTheDocument();
  });
});
