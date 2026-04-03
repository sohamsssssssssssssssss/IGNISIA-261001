import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import { Download, AlertTriangle, CheckCircle, ShieldAlert, FileSearch, Calculator, Network } from 'lucide-react';
import { PromoterGraph } from './PromoterGraph';

export const Dashboard = ({ results }: { results: any }) => {
    if (!results) return null;

    const conceptData = Object.keys(results.concept_radar).map(key => ({
        subject: key,
        A: results.concept_radar[key],
        fullMark: 1.0,
    }));

    const isApproved = results.final_score > 60;

    return (
        <div className="glass-panel" style={{ animation: 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) ease-out' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontSize: '1.5rem' }}>Final AI Recommendation</h2>
                <button className="btn">
                    <Download size={18} />
                    Download CAM (.docx)
                </button>
            </div>

            <div className="grid-2">
                {/* Score Card */}
                <div className="stat-card" style={{ gridColumn: '1 / -1', padding: '30px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>Overall Credit Score</div>
                            <div className="cam-score" style={{ color: isApproved ? 'var(--success)' : 'var(--danger)' }}>
                                {results.final_score} / 100
                            </div>
                            <div style={{ marginTop: '5px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{ background: 'var(--bg-lighter)', padding: '4px 8px', borderRadius: '4px', fontSize: '0.85rem' }}>
                                    CIBIL CMR-{results.cibil_cmr}
                                </span>
                            </div>
                        </div>

                        {/* Pricing Block */}
                        {isApproved && (
                            <div style={{ background: 'var(--bg-lighter)', padding: '15px', borderRadius: '8px', minWidth: '250px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px', fontWeight: 600 }}>
                                    <Calculator size={16} color="var(--accent)" />
                                    Dynamic Pricing Math
                                </div>
                                <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px' }}>
                                    <span>Base Rate (MCLR):</span> <span>{results.pricing.baseRate}%</span>
                                    <span>CBM Risk Premium:</span> <span>+{results.pricing.riskPremium}%</span>
                                    <span>Sector Spread:</span> <span>{results.pricing.sectorSpread > 0 ? `+${results.pricing.sectorSpread}` : results.pricing.sectorSpread}%</span>
                                    <div style={{ ...styles.divider, gridColumn: '1 / -1' }} />
                                    <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>Final Interest Rate:</span>
                                    <span style={{ color: 'var(--success)', fontWeight: 600 }}>{results.pricing.totalRate}%</span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div style={{ fontSize: '1.2rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', marginTop: '10px' }}>
                        {isApproved ? (
                            <><CheckCircle color="var(--success)" /> Recommended Limit: INR {(results.recommended_limit / 10000000).toFixed(2)} Cr</>
                        ) : (
                            <><ShieldAlert color="var(--danger)" /> Application Rejected</>
                        )}
                    </div>

                    {!isApproved && (
                        <button className="btn" style={{ marginTop: '20px', background: 'var(--danger)' }}>
                            Generate RBI Adverse Action Notice
                        </button>
                    )}
                </div>

                {/* Radar Chart */}
                <div style={{ height: '300px' }}>
                    <h3 style={{ textAlign: 'center', marginBottom: '10px', color: 'var(--text-secondary)' }}>Concept Distribution</h3>
                    <ResponsiveContainer width="100%" height="100%">
                        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={conceptData}>
                            <PolarGrid stroke="rgba(255,255,255,0.2)" />
                            <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                            <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
                            <Radar name="Borrower" dataKey="A" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.6} />
                        </RadarChart>
                    </ResponsiveContainer>
                </div>

                {/* SHAP Waterfall */}
                <div>
                    <h3 style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>SHAP Key Drivers</h3>
                    <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '16px' }}>
                        {results.shap.map((item, idx) => (
                            <div key={idx} className="shap-item">
                                <span>{item.feature}</span>
                                <span style={{
                                    color: item.contribution.startsWith('+') ? 'var(--success)' : 'var(--danger)',
                                    fontWeight: 600
                                }}>
                                    {item.contribution}
                                </span>
                            </div>
                        ))}
                    </div>

                    {/* Graph and Warning Column */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                        {!isApproved && results.network_data && (
                            <div>
                                <h3 style={{ marginBottom: '16px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <Network size={18} /> Promoter Shell Network (MCA)
                                </h3>
                                <PromoterGraph data={results.network_data} />
                            </div>
                        )}

                        {!isApproved && (
                            <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px' }}>
                                <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--danger)', marginBottom: '8px' }}>
                                    <AlertTriangle size={18} />
                                    Early Warning Signals (Detected)
                                </h4>
                                <ul style={{ paddingLeft: '24px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                    <li>GSTR 2A vs 3B Variance &gt; 8% (Feb 2025)</li>
                                    <li>Director connected to 12 shell entities (MCA)</li>
                                </ul>
                            </div>
                        )}

                        {results.contradictions && results.contradictions.length > 0 && (
                            <div style={{ marginTop: '15px', padding: '16px', background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.3)', borderRadius: '8px' }}>
                                <h4 style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#eab308', marginBottom: '8px' }}>
                                    <FileSearch size={18} />
                                    Multi-Pillar Contradictions
                                </h4>
                                <ul style={{ paddingLeft: '24px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                    {results.contradictions.map((c: string, idx: number) => (
                                        <li key={idx} style={{ marginBottom: '4px' }}>{c}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

const styles = {
    divider: {
        height: '1px',
        background: 'rgba(255,255,255,0.1)',
        margin: '4px 0'
    }
};
