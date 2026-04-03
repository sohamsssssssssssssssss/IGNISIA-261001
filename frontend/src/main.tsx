import React from 'react';
import ReactDOM from 'react-dom/client';
import { ErrorBoundary } from './components/msme/ErrorBoundary';
import { MSMEScoring } from './components/msme/MSMEScoring';
import './msme.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
    <React.StrictMode>
        <ErrorBoundary>
            <MSMEScoring />
        </ErrorBoundary>
    </React.StrictMode>
);
