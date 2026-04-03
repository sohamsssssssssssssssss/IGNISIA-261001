import React, { useState, useEffect, useRef } from 'react';
import { UploadForm } from './components/UploadForm';
import { Dashboard } from './components/Dashboard';
import { DDNotesForm } from './components/DDNotesForm';
import { Activity, ShieldCheck, Database } from 'lucide-react';

function App() {
    const [pipelineState, setPipelineState] = useState('idle'); // idle, running, complete
    const [logs, setLogs] = useState([]);
    const [borrowerId, setBorrowerId] = useState(null);
    const [results, setResults] = useState(null);
    const [scenario, setScenario] = useState('rejection'); // 'approval' or 'rejection'
    const wsRef = useRef(null);
    const logsEndRef = useRef(null);

    // Auto-scroll logs
    useEffect(() => {
        if (logsEndRef.current) {
            logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs]);

    const handleStartPipeline = (bId: string) => {
        setBorrowerId(bId as any);
        setPipelineState('running');
        setLogs([{ msg: 'Initializing Processing Pipeline...', time: new Date().toLocaleTimeString() }]);

        // Setup Mock WebSocket for the Hackathon Demo
        let step = 0;
        const mockMessages = scenario === 'rejection' ? [
            "Pillar 1: Parsing documents (GSTR, ITR, Banks)...",
            "Pillar 1: Detected 18% GSTR-2A vs 3B Variance (Circular Trading Risk)",
            "Pillar 1: Detected 25% Form 26AS TDS Mismatch",
            "Pillar 2: eCourts Agent flags 1 active DRT case (Arjun Textiles)",
            "Pillar 2: Pulling CIBIL Commercial Score...",
            "Pillar 2: Contradictions Detector: Flagged Revenue Mismatch across GST/Bank/ITR",
            "Pillar 3: Formatting Concept Bottleneck Vector...",
            "Pillar 3: Final CAM Score generated. Creating DOCX...",
            "DONE"
        ] : [
            "Pillar 1: Parsing documents (GSTR, ITR, Banks)...",
            "Pillar 1: GSTR and 26AS match. Bank statements clean.",
            "Pillar 2: eCourts / MCA Checks Passed (0 alerts).",
            "Pillar 2: Pulling CIBIL Commercial Score (CMR-3)...",
            "Pillar 2: Contradictions Detector Passed.",
            "Pillar 3: Formatting Concept Bottleneck Vector...",
            "Pillar 3: Final CAM Score generated. Creating DOCX...",
            "DONE"
        ];

        const interval = setInterval(() => {
            if (step < mockMessages.length) {
                const msg = mockMessages[step];
                if (msg === "DONE") {
                    fetchResults(bId);
                    clearInterval(interval);
                } else {
                    setLogs((prev: any) => [...prev, { msg, time: new Date().toLocaleTimeString() }] as any);
                    step++;
                }
            }
        }, 1500);
    };

    const fetchResults = (bId: string) => {
        // Simulating API Fetch
        if (scenario === 'rejection') {
            setResults({
                borrower_id: bId,
                name: "Arjun Textiles Pvt. Ltd.",
                final_score: 52.0,
                recommended_limit: 0,
                cibil_cmr: 6, // High Risk
                pricing: {
                    baseRate: 8.5,
                    riskPremium: 4.5,
                    sectorSpread: 1.2,
                    totalRate: 14.2
                },
                contradictions: [
                    "GST data shows ₹12 Cr annual revenue. Bank statement shows ₹4 Cr annual credits. Annual Report claims ₹18 Cr turnover. These three don't reconcile — flagging for manual review."
                ],
                network_data: {
                    nodes: [
                        { id: "director", label: "Arjun Singhania (Director)", type: "director", status: "flagged" },
                        { id: "arjun_textiles", label: "Arjun Textiles", type: "company", status: "flagged" },
                        { id: "shell_1", label: "Alpha Trading (Shell)", type: "company", status: "defaulter" },
                        { id: "shell_2", label: "Beta Logistics", type: "company", status: "defaulter" },
                        { id: "shell_3", label: "Gamma Holding", type: "company", status: "flagged" },
                        { id: "shell_4", label: "Delta Services", type: "company", status: "clean" },
                    ],
                    links: [
                        { source: "director", target: "arjun_textiles" },
                        { source: "director", target: "shell_1" },
                        { source: "director", target: "shell_2" },
                        { source: "director", target: "shell_3" },
                        { source: "director", target: "shell_4" },
                        { source: "shell_1", target: "shell_2" },
                        { source: "shell_3", target: "arjun_textiles" },
                    ]
                },
                concept_radar: {
                    "Debt Repayment Ability": 0.4,
                    "Cash Flow Capacity": 0.3,
                    "Capital Strength": 0.5,
                    "Collateral Quality": 0.7,
                    "GST Compliance & Integrity": 0.3
                },
                shap: [
                    { "feature": "18% GSTR ITC Mismatch", "contribution": "-15 pts" },
                    { "feature": "26AS vs ITR Declared Variance (25%)", "contribution": "-12 pts" },
                    { "feature": "3 NACH Returns (12 mo)", "contribution": "-8 pts" },
                    { "feature": "Active DRT Case (45L)", "contribution": "-5 pts" },
                    { "feature": "Low Factory Utilization (40%)", "contribution": "-4 pts" }
                ]
            });
        } else {
            setResults({
                borrower_id: bId,
                name: "CleanTech Manufacturing Ltd.",
                final_score: 88.5,
                recommended_limit: 50000000,
                cibil_cmr: 3, // Low-Medium Risk
                pricing: {
                    baseRate: 8.5,
                    riskPremium: 1.5,
                    sectorSpread: -0.5,
                    totalRate: 9.5
                },
                contradictions: [],
                concept_radar: {
                    "Debt Repayment Ability": 0.9,
                    "Cash Flow Capacity": 0.85,
                    "Capital Strength": 0.9,
                    "Collateral Quality": 0.8,
                    "GST Compliance & Integrity": 0.95
                },
                shap: [
                    { "feature": "High DSCR Buffer", "contribution": "+12 pts" },
                    { "feature": "Zero GSTR Variances", "contribution": "+8 pts" },
                    { "feature": "Clear eCourts / Promoters", "contribution": "+6 pts" }
                ]
            });
        }
        setPipelineState('complete');
    };

    const handleDDUpdate = (notes: any) => {
        // Simulating score update based on DD Notes
        setLogs((prev: any) => [...prev, { msg: `Qualitative DD applied: Management(${notes.managementQuality}/5). Recalculating score...`, time: new Date().toLocaleTimeString() }] as any);

        setTimeout(() => {
            setResults((prev: any) => ({
                ...prev,
                final_score: scenario === 'rejection' ? 49.0 : 89.5,
                concept_radar: {
                    ...prev.concept_radar,
                    "Debt Repayment Ability": 0.95
                },
                shap: [
                    { "feature": "Excellent Management Quality", "contribution": "+6.3 pts" },
                    ...prev.shap
                ]
            }));
        }, 800);
    };

    return (
        <div className="container">
            <div className="header">
                <h1>Intelli-Credit Engine</h1>
                <p>AI-Powered Corporate Credit Appraisal System (India Edition)</p>

                <div style={{ marginTop: '20px', padding: '10px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', display: 'inline-flex', gap: '10px' }}>
                    <span style={{ color: 'var(--text-secondary)', marginRight: '10px' }}>Demo Controls:</span>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
                        <input type="radio" name="scenario" value="rejection" checked={scenario === 'rejection'} onChange={(e) => setScenario(e.target.value)} />
                        Arjun Textiles (Rejection)
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer', marginLeft: '10px' }}>
                        <input type="radio" name="scenario" value="approval" checked={scenario === 'approval'} onChange={(e) => setScenario(e.target.value)} />
                        Clean Borrower (Approval)
                    </label>
                </div>

                <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '20px' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--success)', fontSize: '0.9rem' }}>
                        <Activity size={16} /> Pillar 1: Ingestor Offline
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--success)', fontSize: '0.9rem' }}>
                        <Database size={16} /> Pillar 2: Micro-Agents Ready
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--success)', fontSize: '0.9rem' }}>
                        <ShieldCheck size={16} /> Pillar 3: CBM Model Ready
                    </span>
                </div>
            </div>

            <div className="grid-2">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    {pipelineState === 'idle' && (
                        <UploadForm onStart={handleStartPipeline} />
                    )}

                    {pipelineState !== 'idle' && (
                        <div className="glass-panel" style={pipelineState === 'running' ? { borderColor: 'var(--accent)', animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' } : {}}>
                            <h3 style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
                                Pipeline Execution Logs
                                {pipelineState === 'running' && <Activity size={20} color="var(--accent)" />}
                            </h3>

                            <div className="logs">
                                {logs.map((log: any, i: number) => (
                                    <div key={i} className="log-entry" style={{
                                        color: log.msg.includes('Contradictions') && log.msg.includes('Flagged') ? 'var(--danger)' : 'inherit'
                                    }}>
                                        <span style={{ opacity: 0.5 }}>[{log.time}]</span> {log.msg}
                                    </div>
                                ))}
                                <div ref={logsEndRef} />
                            </div>
                        </div>
                    )}

                    {pipelineState === 'complete' && (
                        <DDNotesForm onSubmit={handleDDUpdate} />
                    )}
                </div>

                <div>
                    {pipelineState === 'complete' ? (
                        <Dashboard results={results} />
                    ) : (
                        <div className="glass-panel" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
                            {pipelineState === 'running' ? 'Computing Concept Maps and SHAP Attributions...' : 'Awaiting Document Upload'}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default App;
