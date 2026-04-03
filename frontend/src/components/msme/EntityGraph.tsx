import React, { useCallback, useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import fcose from 'cytoscape-fcose';

cytoscape.use(fcose);

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const CY_STYLE = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      label: 'data(label)',
      width: 'data(size)',
      height: 'data(size)',
      color: '#f1f5f9',
      'font-size': 10,
      'font-family': 'IBM Plex Sans, system-ui, sans-serif',
      'text-valign': 'bottom',
      'text-margin-y': 6,
      'text-outline-color': '#020617',
      'text-outline-width': 2,
      'border-width': 2,
      'border-color': '#1e293b',
    },
  },
  {
    selector: 'node[is_queried]',
    style: {
      'border-color': '#f87171',
      'border-width': 3,
    },
  },
  {
    selector: 'node[in_cycle]',
    style: {
      'border-color': '#ef4444',
      'border-width': 3,
      'border-style': 'dashed',
    },
  },
  {
    selector: "node[type='director']",
    style: {
      shape: 'ellipse',
      'border-color': '#f59e0b',
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-color': '#818cf8',
      'border-width': 4,
      'overlay-color': '#6366f1',
      'overlay-opacity': 0.15,
    },
  },
  {
    selector: 'edge',
    style: {
      'line-color': 'data(color)',
      width: 'data(width)',
      label: 'data(label)',
      'font-size': 9,
      'font-family': 'IBM Plex Sans, system-ui, sans-serif',
      color: '#94a3b8',
      'text-outline-color': '#020617',
      'text-outline-width': 2,
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
      'curve-style': 'bezier',
      opacity: 0.95,
    },
  },
  {
    selector: 'edge[arrow]',
    style: {
      'target-arrow-shape': 'triangle',
      'target-arrow-color': 'data(color)',
      'arrow-scale': 1.2,
    },
  },
  {
    selector: 'edge[in_cycle]',
    style: {
      'line-style': 'dashed',
      'line-dash-pattern': [8, 4],
      width: 4,
      opacity: 1,
    },
  },
  {
    selector: '.cycle-pulse',
    style: {
      'line-color': '#f87171',
      width: 5,
      opacity: 1,
      'transition-property': 'opacity',
      'transition-duration': '0.6s',
    },
  },
  {
    selector: '.dimmed',
    style: {
      opacity: 0.15,
    },
  },
] as const;

interface CytoscapeElement {
  data: Record<string, any>;
}

interface EntityGraphPayload {
  nodes: CytoscapeElement[];
  edges: CytoscapeElement[];
  meta?: {
    queried_gstin: string;
    total_nodes: number;
    total_edges: number;
    cycles_detected: number;
    cycle_paths: string[][];
    total_cycle_amount: number;
  };
}

interface EntityGraphProps {
  gstin: string;
  graphData?: EntityGraphPayload | null;
}

const NodeDetailPanel: React.FC<{ node: cytoscape.NodeSingular | null; onClose: () => void }> = ({ node, onClose }) => {
  if (!node) return null;
  const d = node.data();

  return (
    <div style={{
      position: 'absolute', top: 16, right: 16, width: 240,
      background: '#0f172a', border: '1px solid #334155',
      borderRadius: 10, padding: 16, zIndex: 10,
      boxShadow: '0 4px 24px rgba(0,0,0,0.6)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 13 }}>
          {d.type === 'director' ? 'Director' : 'Entity'}
        </span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer' }}>
          x
        </button>
      </div>
      <p style={{ color: '#f1f5f9', fontSize: 13, marginBottom: 8 }}>{d.entity_name || d.label}</p>
      {d.gstin && (
        <p style={{ color: '#64748b', fontSize: 11, fontFamily: 'monospace', marginBottom: 6 }}>
          {d.gstin}
        </p>
      )}
      {d.risk_score != null && (
        <div style={{ display: 'flex', justifyContent: 'space-between', background: '#1e293b', borderRadius: 6, padding: '6px 10px', marginBottom: 6 }}>
          <span style={{ color: '#94a3b8', fontSize: 12 }}>Credit Score</span>
          <span style={{ color: d.risk_score >= 550 ? '#22c55e' : '#f87171', fontWeight: 700, fontSize: 13 }}>
            {d.risk_score}
          </span>
        </div>
      )}
      {d.company_count != null && (
        <div style={{ background: '#1e293b', borderRadius: 6, padding: '6px 10px', marginBottom: 6 }}>
          <span style={{ color: '#fbbf24', fontSize: 12 }}>
            Controls {d.company_count} companies simultaneously
          </span>
        </div>
      )}
      {d.in_cycle && (
        <div style={{ background: '#7f1d1d', borderRadius: 6, padding: '6px 10px' }}>
          <span style={{ color: '#fca5a5', fontSize: 12 }}>
            Member of circular transaction topology
          </span>
        </div>
      )}
    </div>
  );
};

export const EntityGraph: React.FC<EntityGraphProps> = ({ gstin, graphData }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const intervalRef = useRef<number | null>(null);
  const [data, setData] = useState<EntityGraphPayload | null>(graphData || null);
  const [selectedNode, setSelectedNode] = useState<cytoscape.NodeSingular | null>(null);
  const [loading, setLoading] = useState(!graphData);
  const [error, setError] = useState<string | null>(null);
  const [cycleAnimActive, setCycleAnimActive] = useState(false);

  useEffect(() => {
    if (graphData) {
      setData(graphData);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/api/v1/entity-graph/${gstin}`)
      .then((r) => {
        if (!r.ok) throw new Error(`Graph API returned ${r.status}`);
        return r.json();
      })
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Graph data unavailable');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [gstin, graphData]);

  useEffect(() => {
    if (!data || !containerRef.current) return;

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...data.nodes, ...data.edges],
      style: CY_STYLE as any,
      layout: {
        name: 'fcose',
        animate: true,
        animationDuration: 800,
        randomize: true,
        idealEdgeLength: 150,
        nodeRepulsion: 8000,
        gravity: 0.25,
        nodeSeparation: 75,
      } as any,
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });

    cy.on('tap', 'node', (evt) => {
      setSelectedNode(evt.target);
      cy.elements().addClass('dimmed');
      evt.target.removeClass('dimmed');
      evt.target.neighborhood().removeClass('dimmed');
    });

    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setSelectedNode(null);
        cy.elements().removeClass('dimmed');
      }
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
    };
  }, [data]);

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
      }
    };
  }, []);

  const toggleCycleAnimation = useCallback(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const cycleEdges = cy.edges('[in_cycle]');

    if (cycleAnimActive) {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
      cycleEdges.removeClass('cycle-pulse');
      intervalRef.current = null;
      setCycleAnimActive(false);
      return;
    }

    let visible = true;
    cycleEdges.addClass('cycle-pulse');
    intervalRef.current = window.setInterval(() => {
      visible = !visible;
      if (visible) {
        cycleEdges.addClass('cycle-pulse');
      } else {
        cycleEdges.removeClass('cycle-pulse');
      }
    }, 700);
    setCycleAnimActive(true);
  }, [cycleAnimActive]);

  const resetView = () => {
    cyRef.current?.fit(undefined, 40);
    setSelectedNode(null);
    cyRef.current?.elements().removeClass('dimmed');
  };

  return (
    <div className="msme-card" style={{ overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingBottom: 14, borderBottom: '1px solid var(--card-border)', flexWrap: 'wrap' }}>
        <div className="msme-card-title" style={{ marginBottom: 0 }}>Entity Network Graph</div>
        {data?.meta && (
          <>
            <span className="msme-inline-meta">{data.meta.total_nodes} entities · {data.meta.total_edges} connections</span>
            {data.meta.cycles_detected > 0 && (
              <span className="msme-risk-pill" style={{ borderColor: 'var(--red)', color: 'var(--red)' }}>
                {data.meta.cycles_detected} circular topology detected
              </span>
            )}
          </>
        )}
        <div style={{ display: 'flex', gap: 8, marginLeft: 'auto' }}>
          {data?.meta?.cycles_detected ? (
            <button className="msme-btn msme-btn--ghost" onClick={toggleCycleAnimation}>
              {cycleAnimActive ? 'Stop animation' : 'Animate cycle'}
            </button>
          ) : null}
          <button className="msme-btn msme-btn--ghost" onClick={resetView}>Reset view</button>
        </div>
      </div>

      <div style={{ position: 'relative', minHeight: 460 }}>
        {loading ? (
          <div className="msme-inline-meta" style={{ paddingTop: 24 }}>Building entity graph...</div>
        ) : null}
        {error ? (
          <div className="msme-alert msme-alert--danger" style={{ marginTop: 16 }}>{error}</div>
        ) : null}
        <div ref={containerRef} style={{ width: '100%', height: 460, display: loading || error ? 'none' : 'block' }} />
        {selectedNode ? (
          <NodeDetailPanel
            node={selectedNode}
            onClose={() => {
              setSelectedNode(null);
              cyRef.current?.elements().removeClass('dimmed');
            }}
          />
        ) : null}
      </div>

      {!loading && !error && data?.meta?.cycles_detected ? (
        <div className="msme-alert msme-alert--danger" style={{ marginTop: 14 }}>
          Circular topology path: {data.meta.cycle_paths[0]?.join(' → ')} → (back to start)
        </div>
      ) : null}
      {!loading && !error ? (
        <div className="msme-footer-stats">
          <span style={{ color: '#ef4444' }}>● Queried GSTIN</span>
          <span style={{ color: '#dc2626' }}>● In fraud cycle</span>
          <span style={{ color: '#f59e0b' }}>● Director / promoter</span>
          <span style={{ color: '#475569' }}>● Connected entity</span>
          <span>Drag to pan · Scroll to zoom · Click node for details</span>
        </div>
      ) : null}
    </div>
  );
};

export default EntityGraph;
