import { useLocation, useNavigate } from 'react-router-dom';
import './ApiDocsPage.css';

function resolveApiDocsUrl(): string {
  const configuredDocsUrl = import.meta.env.VITE_API_DOCS_URL?.trim();
  if (configuredDocsUrl) {
    return configuredDocsUrl;
  }

  const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();
  if (configuredApiUrl) {
    try {
      const url = new URL(configuredApiUrl, window.location.origin);
      return new URL('/docs', url.origin).toString();
    } catch {
      // Fall through to default
    }
  }

  return '/docs';
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
