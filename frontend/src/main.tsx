import React from 'react';
import ReactDOM from 'react-dom/client';
import { ErrorBoundary } from './components/msme/ErrorBoundary';
import { MSMEScoring } from './components/msme/MSMEScoring';
import InsightsPage from './pages/InsightsPage';
import './msme.css';

type AppRoute = 'scoring' | 'insights';

function resolveRoute(pathname: string): AppRoute {
  return pathname.startsWith('/insights') ? 'insights' : 'scoring';
}

function navigateTo(pathname: string) {
  window.history.pushState({}, '', pathname);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function AppShell() {
  const [route, setRoute] = React.useState<AppRoute>(() => resolveRoute(window.location.pathname));

  React.useEffect(() => {
    const handleRouteChange = () => {
      setRoute(resolveRoute(window.location.pathname));
    };

    window.addEventListener('popstate', handleRouteChange);
    return () => window.removeEventListener('popstate', handleRouteChange);
  }, []);

  return (
    <div className="msme-app">
      <div className="msme-topbar">
        <div className="msme-shell-brand">
          <div className="msme-wordmark">INTELLI-CREDIT <span>MSME Scoring Engine</span></div>
          <div className="msme-shell-version">v1.0 — REAL-TIME ASSESSMENT</div>
        </div>

        <nav className="msme-nav" aria-label="Main dashboard tabs">
          <button
            type="button"
            className={`msme-nav__item ${route === 'scoring' ? 'is-active' : ''}`}
            onClick={() => navigateTo('/')}
          >
            Scoring
          </button>
          <button
            type="button"
            className={`msme-nav__item ${route === 'insights' ? 'is-active' : ''}`}
            onClick={() => navigateTo('/insights')}
          >
            Insights
          </button>
        </nav>
      </div>

      {route === 'insights' ? (
        <InsightsPage onNavigateToScoring={() => navigateTo('/')} />
      ) : (
        <MSMEScoring showTopbar={false} />
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
    <React.StrictMode>
        <ErrorBoundary>
            <AppShell />
        </ErrorBoundary>
    </React.StrictMode>
);
