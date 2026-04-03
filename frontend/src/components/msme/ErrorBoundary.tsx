import React from 'react';

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  constructor(props: React.PropsWithChildren) {
    super(props);
    this.state = { hasError: false, message: '' };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      message: error?.message || 'Unexpected UI failure',
    };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('MSME UI error boundary', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="msme-app">
          <div className="msme-container">
            <div className="msme-card">
              <div className="msme-card-title">Application Error</div>
              <div className="msme-alert msme-alert--danger">
                A section of the scoring dashboard crashed. Refresh the page or retry the last GSTIN lookup.
              </div>
              <div className="msme-inline-meta" style={{ marginTop: 12 }}>
                {this.state.message}
              </div>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
