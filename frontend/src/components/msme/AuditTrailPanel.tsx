import React, { useEffect, useRef, useState } from 'react';

interface AuditEntry {
  timestamp: string;
  message: string;
}

interface AuditTrailPanelProps {
  entries: AuditEntry[];
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleTimeString('en-IN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }) + `.${String(date.getMilliseconds()).padStart(3, '0')}`;
}

function lineColor(message: string): string | undefined {
  const text = message.toLowerCase();
  if (text.includes('penalty') || text.includes('cycle detected')) return 'var(--red)';
  if (text.includes('sparse') || text.includes('risk band')) return 'var(--amber)';
  if (text.includes('complete')) return 'var(--green)';
  return undefined;
}

export const AuditTrailPanel: React.FC<AuditTrailPanelProps> = ({ entries }) => {
  const [visibleEntries, setVisibleEntries] = useState<AuditEntry[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setVisibleEntries([]);
    if (!entries?.length) return;

    let index = 0;
    const timer = window.setInterval(() => {
      index += 1;
      setVisibleEntries(entries.slice(0, index));
      if (index >= entries.length) {
        window.clearInterval(timer);
      }
    }, 120);

    return () => window.clearInterval(timer);
  }, [entries]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [visibleEntries]);

  return (
    <div className="msme-card">
      <div className="msme-card-title">Audit Trail</div>
      <div className="msme-inline-meta" style={{ marginBottom: 12 }}>
        Live decision trace for explainability, compliance, and demo visibility
      </div>
      <div className="msme-log-wrap">
        <div className="msme-log-inner" ref={logRef}>
          {visibleEntries.length === 0 && (
            <div className="msme-log-line" style={{ color: 'var(--text-dim)' }}>
              Awaiting scoring response...
            </div>
          )}
          {visibleEntries.map((entry, index) => (
            <div key={`${entry.timestamp}-${index}`} className="msme-log-line" style={{ color: lineColor(entry.message) }}>
              <span className="msme-log-time">{formatTimestamp(entry.timestamp)}</span> {entry.message}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
