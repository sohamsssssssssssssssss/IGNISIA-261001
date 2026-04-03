import React from 'react';
import { AlertTriangle, OctagonAlert } from 'lucide-react';

type ExecutionMode = 'disabled' | 'reduced' | 'full';

interface RagCapabilities {
  execution_mode: ExecutionMode;
  degradations?: string[];
}

interface HealthPayload {
  rag?: RagCapabilities;
}

interface RuntimeStatusBannerProps {
  apiBase: string;
  apiToken?: string;
}

const DEGRADATION_LABELS: Record<string, string> = {
  local_generation_unavailable: 'local generation',
  web_intel_unavailable: 'web intelligence',
};

function formatDegradations(items: string[] = []): string {
  const labels = items.map((item) => DEGRADATION_LABELS[item] ?? item.replace(/_/g, ' '));
  if (labels.length === 0) return 'optional enrichments';
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(', ')}, and ${labels[labels.length - 1]}`;
}

function buildRuntimeHeaders(apiToken?: string): Record<string, string> {
  if (!apiToken) return {};
  return { Authorization: `Bearer ${apiToken}` };
}

export const RuntimeStatusBanner: React.FC<RuntimeStatusBannerProps> = ({ apiBase, apiToken }) => {
  const [capabilities, setCapabilities] = React.useState<RagCapabilities | null>(null);

  React.useEffect(() => {
    let active = true;

    const loadRuntimeStatus = async () => {
      try {
        const response = await fetch(`${apiBase}/health`, {
          headers: buildRuntimeHeaders(apiToken),
        });
        if (!response.ok) return;
        const payload = await response.json() as HealthPayload;
        if (active) {
          setCapabilities(payload.rag ?? null);
        }
      } catch {
        if (active) {
          setCapabilities(null);
        }
      }
    };

    loadRuntimeStatus();
    return () => {
      active = false;
    };
  }, [apiBase, apiToken]);

  if (!capabilities || capabilities.execution_mode === 'full') {
    return null;
  }

  const isDisabled = capabilities.execution_mode === 'disabled';
  const degradationText = formatDegradations(capabilities.degradations);

  return (
    <div
      className={`msme-alert ${isDisabled ? 'msme-alert--danger' : 'msme-alert--warning'}`}
      style={{ marginBottom: 20 }}
      role="status"
    >
      {isDisabled ? <OctagonAlert size={14} /> : <AlertTriangle size={14} />}
      <div>
        <strong>{isDisabled ? 'Document RAG runtime unavailable.' : 'Document RAG runtime in reduced mode.'}</strong>{' '}
        {isDisabled
          ? 'Corporate CAM generation is offline until the retrieval runtime is restored.'
          : `Corporate CAM generation will continue, but ${degradationText} is currently skipped.`}
        {' '}MSME scoring remains available.
      </div>
    </div>
  );
};
