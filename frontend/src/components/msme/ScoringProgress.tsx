import React from 'react';

interface ScoringProgressProps {
  steps: string[];
  activeIndex: number;
}

export const ScoringProgress: React.FC<ScoringProgressProps> = ({ steps, activeIndex }) => (
  <div className="msme-card">
    <div className="msme-card-title">Scoring Progress</div>
    <div className="msme-progress-steps">
      {steps.map((step, index) => {
        const state = index < activeIndex ? 'done' : index === activeIndex ? 'active' : 'idle';
        return (
          <div className={`msme-progress-step msme-progress-step--${state}`} key={step}>
            <div className="msme-progress-dot" />
            <div className="msme-progress-copy">
              <div className="msme-progress-label">{step}</div>
              <div className="msme-progress-state">
                {state === 'done' ? 'Complete' : state === 'active' ? 'Running' : 'Pending'}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  </div>
);
