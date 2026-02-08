import { useLocation, useNavigate } from 'react-router-dom';
import './ApiDocsPage.css';

const DEFAULT_API_DOCS_URL = 'http://localhost:8000/docs';

function resolveApiDocsUrl(): string {
  const configuredDocsUrl = import.meta.env.VITE_API_DOCS_URL?.trim();
  if (configuredDocsUrl) {
    return configuredDocsUrl;
  }

  const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();
  if (configuredApiUrl) {
    try {
      return new URL('/docs', new URL(configuredApiUrl).origin).toString();
    } catch {
      // Ignore invalid or relative API URLs and use the local backend default.
    }
  }

  return DEFAULT_API_DOCS_URL;
}

export function ApiDocsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const apiDocsUrl = resolveApiDocsUrl();
  const from = typeof location.state === 'object' && location.state !== null && 'from' in location.state
    && typeof (location.state as { from?: unknown }).from === 'string'
    ? (location.state as { from: string }).from
    : null;

  const handleBack = () => {
    if (from) {
      navigate(from, { replace: true });
      return;
    }

    if (window.history.length > 1) {
      navigate(-1);
      return;
    }

    navigate('/map', { replace: true });
  };

  return (
    <section className="api-docs-page">
      <div className="api-docs-toolbar">
        <button
          type="button"
          className="api-docs-back-button"
          onClick={handleBack}
        >
          Back
        </button>
      </div>
      <iframe
        title="Backend API docs"
        src={apiDocsUrl}
        className="api-docs-frame"
      />
    </section>
  );
}
