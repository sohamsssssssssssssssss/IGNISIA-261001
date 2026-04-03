import React, { useState } from 'react';
import { UploadCloud, File, Play } from 'lucide-react';

export const UploadForm = ({ onStart }: { onStart: (id: string) => void }) => {
  const [files, setFiles] = useState<any[]>([]);

  const handleDrop = (e: any) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...dropped]);
  };

  const handleFileSelect = (e: any) => {
    const selected = Array.from(e.target.files);
    setFiles(prev => [...prev, ...selected]);
  };

  const startPipeline = () => {
    if (files.length === 0) return;
    const borrowerId = "BOR_" + Math.random().toString(36).substr(2, 9);
    onStart(borrowerId);
  };

  return (
    <div className="glass-panel" style={{ marginBottom: '24px' }}>
      <h2 style={{ marginBottom: '16px', fontSize: '1.2rem' }}>1. Document Ingestion</h2>

      <div
        className="upload-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
      >
        <UploadCloud className="upload-icon" />
        <h3>Drag & Drop Financial Documents</h3>
        <p style={{ color: 'var(--text-secondary)', margin: '8px 0 16px' }}>
          GSTR JSONs, ITR-6 XML, Bank Statements CSV, Scanned PDFs
        </p>

        <input
          type="file"
          multiple
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          id="file-upload"
        />
        <label htmlFor="file-upload" className="btn" style={{ background: 'rgba(255,255,255,0.1)', boxShadow: 'none' }}>
          Browse Files
        </label>
      </div>

      {files.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h4 style={{ marginBottom: '8px', color: 'var(--text-secondary)' }}>Selected Files ({files.length})</h4>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '20px' }}>
            {files.map((file, i) => (
              <div key={i} style={{
                background: 'rgba(255,255,255,0.05)',
                padding: '8px 12px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.9rem'
              }}>
                <File size={16} color="var(--accent)" />
                {file.name}
              </div>
            ))}
          </div>

          <button className="btn" onClick={startPipeline} style={{ width: '100%', justifyContent: 'center' }}>
            <Play size={18} />
            Kickoff Analytics Pipeline
          </button>
        </div>
      )}
    </div>
  );
};
