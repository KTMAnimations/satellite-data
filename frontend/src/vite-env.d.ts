/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_API_DOCS_URL?: string;
  readonly VITE_BASE_PATH?: string;
  readonly VITE_MAPTILER_KEY?: string;
  readonly VITE_ROUTER_MODE?: 'browser' | 'hash';
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
