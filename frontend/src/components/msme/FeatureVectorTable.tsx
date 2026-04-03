import React from 'react';

interface FeatureVectorTableProps {
  featureVector: Record<string, number>;
}

export const FeatureVectorTable: React.FC<FeatureVectorTableProps> = ({ featureVector }) => {
  const entries = Object.entries(featureVector).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="msme-card">
      <div className="msme-card-title">Raw Feature Vector</div>
      <div className="msme-feature-table">
        <div className="msme-feature-row msme-feature-row--header">
          <span>Feature</span>
          <span>Value</span>
        </div>
        {entries.map(([key, value]) => (
          <div className="msme-feature-row" key={key}>
            <span className="msme-feature-key">{key}</span>
            <span className="msme-feature-value">{typeof value === 'number' ? value.toFixed(4) : String(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
