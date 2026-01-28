import axios from 'axios';

export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as unknown;
    if (typeof data === 'string' && data.trim()) return data;
    if (data && typeof data === 'object') {
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === 'string' && detail.trim()) return detail;
    }
    return error.message || 'Request failed';
  }

  if (error instanceof Error) return error.message;
  return 'Unknown error';
}

