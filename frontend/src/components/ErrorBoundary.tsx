import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#78716C' }}>
          <h2 style={{ margin: '0 0 0.5rem', fontSize: '1.25rem', color: '#292524' }}>
            Something went wrong
          </h2>
          <p style={{ margin: '0 0 1rem', fontSize: '0.875rem' }}>
            {this.state.error?.message ?? 'An unexpected error occurred.'}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              padding: '0.5rem 1rem',
              border: '1px solid #D6D3D1',
              borderRadius: '6px',
              background: '#FAFAF9',
              cursor: 'pointer',
              fontSize: '0.875rem',
            }}
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
