import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

function normalizeBase(base: string | undefined): string | undefined {
  if (!base) return undefined;
  let normalized = base.trim();
  if (!normalized) return undefined;
  if (!normalized.startsWith('/')) normalized = `/${normalized}`;
  normalized = normalized.replace(/^\/{2,}/, '/');
  if (!normalized.endsWith('/')) normalized = `${normalized}/`;
  normalized = normalized.replace(/\/{2,}$/, '/');
  return normalized;
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());
  const base = normalizeBase(env.VITE_BASE_PATH) ?? '/';

  return {
    base,
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  };
});
