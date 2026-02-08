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
  const apiDocsUrl = resolveApiDocsUrl();

  return (
    <section className="api-docs-page">
      <iframe
        title="Backend API docs"
        src={apiDocsUrl}
        className="api-docs-frame"
      />
    </section>
  );
}
