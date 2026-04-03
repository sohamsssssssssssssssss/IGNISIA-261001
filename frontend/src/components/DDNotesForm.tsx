import React, { useState } from 'react';
import { Send, FileText } from 'lucide-react';

export const DDNotesForm = ({ onSubmit }: { onSubmit: (data: any) => void }) => {
    const [formData, setFormData] = useState({
        managementQuality: 3,
        factoryUtilization: '',
        rptConcerns: '',
        keyManRisk: 'Medium',
        segment: 'Micro'
    });

    const handleSubmit = (e: any) => {
        e.preventDefault();
        onSubmit(formData);
    };

    return (
        <div className="glass-panel" style={{ marginTop: '24px' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <FileText size={20} color="var(--accent)" />
                Qualitative Due Diligence Notes
            </h3>

            <form onSubmit={handleSubmit}>
                <div className="grid-2">
                    <div className="form-group">
                        <label>MSME Segment (Classification)</label>
                        <select
                            value={formData.segment}
                            onChange={(e) => setFormData({ ...formData, segment: e.target.value })}
                        >
                            <option>Micro</option>
                            <option>Small</option>
                            <option>Medium</option>
                            <option>Non-MSME</option>
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Management Quality (1-5)</label>
                        <input
                            type="range"
                            min="1" max="5"
                            value={formData.managementQuality}
                            onChange={(e) => setFormData({ ...formData, managementQuality: Number(e.target.value) })}
                            style={{ width: '100%', marginTop: '16px' }}
                        />
                        <div style={{ textAlign: 'right', fontSize: '0.9rem' }}>{formData.managementQuality} / 5</div>
                    </div>

                    <div className="form-group">
                        <label>Factory Utilization (%)</label>
                        <input
                            type="number"
                            placeholder="e.g. 75"
                            value={formData.factoryUtilization}
                            onChange={(e) => setFormData({ ...formData, factoryUtilization: e.target.value })}
                        />
                    </div>

                    <div className="form-group">
                        <label>Key Man Risk</label>
                        <select
                            value={formData.keyManRisk}
                            onChange={(e) => setFormData({ ...formData, keyManRisk: e.target.value })}
                        >
                            <option>Low</option>
                            <option>Medium</option>
                            <option>High</option>
                        </select>
                    </div>
                </div>

                <div className="form-group">
                    <label>Related Party Transaction (RPT) Concerns / Notes</label>
                    <textarea
                        rows={3}
                        placeholder="Enter any qualitative observations..."
                        value={formData.rptConcerns}
                        onChange={(e) => setFormData({ ...formData, rptConcerns: e.target.value })}
                    ></textarea>
                </div>

                <button type="submit" className="btn" style={{ width: '100%', justifyContent: 'center' }}>
                    <Send size={16} /> Update Feature Vector & Score
                </button>
            </form>
        </div>
    );
};
