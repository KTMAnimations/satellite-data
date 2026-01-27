import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, HashRouter } from 'react-router-dom';
import App from './App';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000, // 2 minutes - data considered fresh
      gcTime: 5 * 60 * 1000, // 5 minutes - garbage collect unused cache (reduced for memory)
      retry: 1,
      refetchOnWindowFocus: false, // Reduce unnecessary refetches
      refetchOnReconnect: false, // Don't refetch on reconnect
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {import.meta.env.VITE_ROUTER_MODE === 'hash' ? (
        <HashRouter
          basename={import.meta.env.BASE_URL}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <App />
        </HashRouter>
      ) : (
        <BrowserRouter
          basename={import.meta.env.BASE_URL}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <App />
        </BrowserRouter>
      )}
    </QueryClientProvider>
  </React.StrictMode>
);
