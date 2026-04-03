import React from 'react';
import { FileUp, Play, RefreshCcw, FileSearch, ShieldAlert, Download } from 'lucide-react';

import { RuntimeStatusBanner } from '../components/msme/RuntimeStatusBanner';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_TOKEN = import.meta.env.VITE_API_TOKEN || '';

const DOC_TYPES = [
  'ALM',
  'SHAREHOLDING_PATTERN',
  'BORROWING_PROFILE',
  'ANNUAL_REPORT',
  'PORTFOLIO_CUTS',
] as const;

type Classification = {
  filename: string;
  predicted_type: string;
  confirmed_type?: string | null;
  confidence: number;
  evidence: string;
  status: string;
};

type PipelineEvent = {
  id: number;
  stage: string;
  event_type: string;
  message: string | null;
  created_at: string;
  metadata?: Record<string, any>;
};

type PipelineStatus = {
  session_id: string;
  workflow_status: string;
  company_name?: string | null;
  updated_at: string;
  last_error?: string | null;
  cam_download_url?: string | null;
  classifications: Classification[];
  latest_run?: {
    run_id: string;
    status: string;
    stage: string;
    chunks_indexed: number;
    error_message?: string | null;
    result?: any;
    events?: PipelineEvent[];
  } | null;
  rag_capabilities?: {
    execution_mode: 'disabled' | 'reduced' | 'full';
    degradations?: string[];
  };
};

function buildHeaders(): Record<string, string> {
  if (!API_TOKEN) return {};
  return { Authorization: `Bearer ${API_TOKEN}` };
}

function withAuthQuery(url: string): string {
  if (!API_TOKEN) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}token=${encodeURIComponent(API_TOKEN)}`;
}

function formatTimestamp(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function CorporateCamPage() {
  const [files, setFiles] = React.useState<File[]>([]);
  const [status, setStatus] = React.useState<PipelineStatus | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);
  const [running, setRunning] = React.useState(false);
  const [refreshing, setRefreshing] = React.useState(false);
  const [classifications, setClassifications] = React.useState<Classification[]>([]);
  const [form, setForm] = React.useState({
    company_name: '',
    pan: '',
    sector: '',
    promoter: '',
    loan_type: 'Term Loan',
    loan_amount: '',
    loan_tenure: '',
    loan_rate: '',
  });

  const sessionId = status?.session_id ?? null;

  const loadStatus = React.useCallback(async (targetSessionId: string) => {
    const response = await fetch(`${API_BASE}/api/pipeline/${encodeURIComponent(targetSessionId)}`, {
      headers: buildHeaders(),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Status request failed with ${response.status}`);
    }
    const payload = await response.json() as PipelineStatus;
    setStatus(payload);
    setClassifications(payload.classifications);
    if (payload.company_name) {
      setForm((current) => ({ ...current, company_name: payload.company_name || current.company_name }));
    }
  }, []);

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Select one or more documents before uploading.');
      return;
    }
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));

      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        headers: buildHeaders(),
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail?.message || body.detail || `Upload failed with ${response.status}`);
      }
      const payload = await response.json();
      setClassifications(payload.classifications);
      await loadStatus(payload.session_id);
    } catch (err: any) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleConfirm = async () => {
    if (!sessionId) return;
    setConfirming(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('session_id', sessionId);
      formData.append('confirmations', JSON.stringify(classifications.map((item) => ({
        filename: item.filename,
        predicted_type: item.predicted_type,
        confirmed_type: item.confirmed_type || item.predicted_type,
      }))));

      const response = await fetch(`${API_BASE}/api/upload/confirm`, {
        method: 'POST',
        headers: buildHeaders(),
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Confirmation failed with ${response.status}`);
      }
      await loadStatus(sessionId);
    } catch (err: any) {
      setError(err.message || 'Failed to confirm classifications');
    } finally {
      setConfirming(false);
    }
  };

  const handleRun = async () => {
    if (!sessionId) return;
    if (!form.company_name.trim()) {
      setError('Company name is required before running the CAM workflow.');
      return;
    }
    setRunning(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('session_id', sessionId);
      Object.entries(form).forEach(([key, value]) => formData.append(key, value));

      const response = await fetch(`${API_BASE}/api/pipeline/run`, {
        method: 'POST',
        headers: buildHeaders(),
        body: formData,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = body.detail?.message || body.detail || `Pipeline run failed with ${response.status}`;
        throw new Error(detail);
      }
      await loadStatus(sessionId);
    } catch (err: any) {
      setError(err.message || 'Pipeline execution failed');
      await loadStatus(sessionId).catch(() => undefined);
    } finally {
      setRunning(false);
    }
  };

  const handleRefresh = async () => {
    if (!sessionId) return;
    setRefreshing(true);
    setError(null);
    try {
      await loadStatus(sessionId);
    } catch (err: any) {
      setError(err.message || 'Failed to refresh status');
    } finally {
      setRefreshing(false);
    }
  };

  const latestRun = status?.latest_run;
  const resultPayload = latestRun?.result ?? null;
  const provenanceDocuments = resultPayload?.provenance_summary?.documents ?? [];
  const queryReports = resultPayload?.web_intel?.query_reports ?? [];

  return (
    <div className="msme-container">
      <RuntimeStatusBanner apiBase={API_BASE} apiToken={API_TOKEN} />

      <div className="msme-card">
        <div className="msme-card-title">Corporate CAM Workflow</div>
        <div style={{ color: 'var(--text-dim)', fontSize: 13, lineHeight: 1.7, marginBottom: 16 }}>
          Persisted document upload, analyst confirmation, RAG execution, and CAM generation for the corporate appraisal flow.
        </div>
        <div className="msme-search-wrap">
          <div className="msme-search-field">
            <label>Upload 1–5 Documents</label>
            <input
              className="msme-input"
              type="file"
              multiple
              onChange={(event) => setFiles(Array.from(event.target.files || []))}
            />
          </div>
          <button className="msme-btn" onClick={handleUpload} disabled={uploading}>
            <FileUp size={14} />
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
          {sessionId && (
            <button className="msme-btn msme-btn--ghost" onClick={handleRefresh} disabled={refreshing}>
              <RefreshCcw size={14} className={refreshing ? 'msme-spin' : ''} />
              Refresh Status
            </button>
          )}
        </div>
        {files.length > 0 && (
          <div className="msme-inline-meta" style={{ marginTop: 12 }}>
            {files.length} file(s) staged for upload
          </div>
        )}
        {sessionId && (
          <div className="msme-inline-meta" style={{ marginTop: 12 }}>
            Session: {sessionId} · Workflow: {status?.workflow_status || 'uploaded'}
          </div>
        )}
      </div>

      {error && (
        <div className="msme-alert msme-alert--danger" style={{ marginBottom: 20 }}>
          <ShieldAlert size={14} />
          {error}
        </div>
      )}

      {classifications.length > 0 && (
        <div className="msme-card">
          <div className="msme-card-title">Classification Review</div>
          <div style={{ display: 'grid', gap: 12 }}>
            {classifications.map((item, index) => (
              <div key={item.filename} className="msme-metric-card" style={{ textAlign: 'left' }}>
                <div className="msme-metric-label">{item.filename}</div>
                <div className="msme-inline-meta" style={{ marginBottom: 8 }}>
                  Predicted: {item.predicted_type} · Confidence: {(item.confidence * 100).toFixed(0)}% · Status: {item.status}
                </div>
                <div style={{ color: 'var(--text-dim)', fontSize: 12, marginBottom: 10 }}>{item.evidence}</div>
                <label style={{ display: 'block', fontFamily: 'var(--mono)', fontSize: 10, marginBottom: 6, color: 'var(--gold)' }}>
                  Confirmed Type
                </label>
                <select
                  className="msme-input"
                  value={item.confirmed_type || item.predicted_type}
                  onChange={(event) => {
                    const next = [...classifications];
                    next[index] = { ...item, confirmed_type: event.target.value };
                    setClassifications(next);
                  }}
                >
                  {DOC_TYPES.map((docType) => (
                    <option key={docType} value={docType}>{docType}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16 }}>
            <button className="msme-btn" onClick={handleConfirm} disabled={confirming}>
              <FileSearch size={14} />
              {confirming ? 'Confirming...' : 'Confirm Classifications'}
            </button>
          </div>
        </div>
      )}

      {sessionId && (
        <div className="msme-grid-2">
          <div className="msme-card">
            <div className="msme-card-title">Application Inputs</div>
            <div style={{ display: 'grid', gap: 12 }}>
              {[
                ['company_name', 'Company Name'],
                ['promoter', 'Promoter'],
                ['sector', 'Sector'],
                ['pan', 'PAN'],
                ['loan_type', 'Loan Type'],
                ['loan_amount', 'Loan Amount'],
                ['loan_tenure', 'Loan Tenure'],
                ['loan_rate', 'Loan Rate'],
              ].map(([key, label]) => (
                <div key={key}>
                  <label style={{ display: 'block', fontFamily: 'var(--mono)', fontSize: 10, marginBottom: 6, color: 'var(--gold)' }}>
                    {label}
                  </label>
                  <input
                    className="msme-input"
                    value={(form as Record<string, string>)[key]}
                    onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
                  />
                </div>
              ))}
            </div>
            <div style={{ marginTop: 16 }}>
              <button className="msme-btn" onClick={handleRun} disabled={running || status?.workflow_status === 'uploaded'}>
                <Play size={14} />
                {running ? 'Executing...' : 'Run CAM Workflow'}
              </button>
            </div>
          </div>

          <div className="msme-card">
            <div className="msme-card-title">Status Snapshot</div>
            <div className="msme-inline-meta" style={{ marginBottom: 8 }}>
              Workflow: {status?.workflow_status || '—'}
            </div>
            <div className="msme-inline-meta" style={{ marginBottom: 8 }}>
              Updated: {formatTimestamp(status?.updated_at)}
            </div>
            <div className="msme-inline-meta" style={{ marginBottom: 8 }}>
              Runtime: {status?.rag_capabilities?.execution_mode || 'unknown'}
            </div>
            {status?.last_error && (
              <div className="msme-alert msme-alert--danger" style={{ marginTop: 12 }}>
                <ShieldAlert size={12} />
                {status.last_error}
              </div>
            )}
            {status?.cam_download_url && (
              <a
                className="msme-btn msme-btn--ghost"
                style={{ marginTop: 12 }}
                href={withAuthQuery(`${API_BASE}${status.cam_download_url}`)}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={14} />
                Download CAM
              </a>
            )}
          </div>
        </div>
      )}

      {latestRun && (
        <>
          <div className="msme-grid-2">
            <div className="msme-card">
              <div className="msme-card-title">Pipeline Timeline</div>
              <div style={{ display: 'grid', gap: 10 }}>
                {(latestRun.events || []).map((event) => (
                  <div key={event.id} className="msme-metric-card" style={{ textAlign: 'left' }}>
                    <div className="msme-metric-label">{event.stage.replace(/_/g, ' ')}</div>
                    <div className="msme-inline-meta" style={{ marginBottom: 6 }}>
                      {event.event_type.toUpperCase()} · {formatTimestamp(event.created_at)}
                    </div>
                    <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>{event.message || 'No detail recorded.'}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="msme-card">
              <div className="msme-card-title">Run Output</div>
              <div className="msme-inline-meta" style={{ marginBottom: 8 }}>
                Stage: {latestRun.stage} · Status: {latestRun.status} · Chunks Indexed: {latestRun.chunks_indexed}
              </div>
              {resultPayload?.web_intel && (
                <div className={`msme-alert ${resultPayload.web_intel.status === 'completed' ? 'msme-alert--success' : 'msme-alert--warning'}`} style={{ marginTop: 12, marginBottom: 12 }}>
                  <ShieldAlert size={12} />
                  Web intelligence: {resultPayload.web_intel.status}
                  {resultPayload.web_intel.skipped_reason ? ` (${resultPayload.web_intel.skipped_reason})` : ''}
                </div>
              )}
              {provenanceDocuments.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div className="msme-card-title" style={{ marginBottom: 8 }}>Indexed Provenance</div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {provenanceDocuments.map((item: any) => (
                      <div key={item.document_id} className="msme-inline-meta">
                        {item.doc_type}: {item.document_id} · {item.chunks_indexed} chunk(s)
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {queryReports.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div className="msme-card-title" style={{ marginBottom: 8 }}>External Query Trace</div>
                  <div style={{ display: 'grid', gap: 10 }}>
                    {queryReports.map((report: any, index: number) => (
                      <div key={`${report.query_type}-${index}`} className="msme-metric-card" style={{ textAlign: 'left' }}>
                        <div className="msme-metric-label">{report.query_type.replace(/_/g, ' ')}</div>
                        <div className="msme-inline-meta" style={{ marginBottom: 6 }}>
                          {report.status} · {report.results_indexed} chunk(s)
                        </div>
                        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>{report.key_finding}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
