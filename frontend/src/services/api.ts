import axios, { AxiosInstance } from 'axios';
import type {
  Region,
  RegionListResponse,
  MetricsResponse,
  AnalysisRequest,
  AnalysisStatus,
  AnalysisResponse,
  CompareRequest,
  CompareResponse,
  ExportRequest,
  ExportResponse,
  AnimationRequest,
  APIKeyCreate,
  APIKeyResponse,
  RegionBounds,
  GeoJSONPolygon,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

class APIClient {
  private client: AxiosInstance;
  private apiKey: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    // Add API key to requests if available
    this.client.interceptors.request.use((config) => {
      if (this.apiKey) {
        config.headers['X-API-Key'] = this.apiKey;
      }
      return config;
    });
  }

  setApiKey(key: string | null) {
    this.apiKey = key;
  }

  // Regions
  async listRegions(params?: {
    page?: number;
    page_size?: number;
    type?: string;
    category?: string;
    country?: string;
    search?: string;
  }): Promise<RegionListResponse> {
    const response = await this.client.get<RegionListResponse>('/regions', { params });
    return response.data;
  }

  async getRegion(id: string): Promise<Region> {
    const response = await this.client.get<Region>(`/regions/${id}`);
    return response.data;
  }

  async createRegion(data: {
    name: string;
    description?: string;
    geometry: GeoJSONPolygon;
    country?: string;
    state_province?: string;
  }): Promise<Region> {
    const response = await this.client.post<Region>('/regions', data);
    return response.data;
  }

  async deleteRegion(id: string): Promise<void> {
    await this.client.delete(`/regions/${id}`);
  }

  // Metrics
  async getMetrics(
    regionId: string,
    params?: {
      start_date?: string;
      end_date?: string;
      metrics?: string[];
      granularity?: 'daily' | 'weekly' | 'monthly';
    }
  ): Promise<MetricsResponse> {
    const response = await this.client.get<MetricsResponse>(`/metrics/${regionId}`, {
      params,
    });
    return response.data;
  }

  // Analysis
  async requestAnalysis(data: AnalysisRequest): Promise<AnalysisStatus> {
    const response = await this.client.post<AnalysisStatus>('/analysis', data);
    return response.data;
  }

  async getAnalysisStatus(id: string): Promise<AnalysisStatus> {
    const response = await this.client.get<AnalysisStatus>(`/analysis/${id}/status`);
    return response.data;
  }

  async getRegionAnalyses(
    regionId: string,
    analysisType?: string
  ): Promise<AnalysisResponse[]> {
    const response = await this.client.get<AnalysisResponse[]>(`/analysis/${regionId}`, {
      params: { analysis_type: analysisType },
    });
    return response.data;
  }

  async comparePeriods(data: CompareRequest): Promise<CompareResponse> {
    const response = await this.client.post<CompareResponse>('/analysis/compare', data);
    return response.data;
  }

  // Exports
  async exportPdf(data: ExportRequest): Promise<ExportResponse> {
    const response = await this.client.post<ExportResponse>('/exports/pdf', data);
    return response.data;
  }

  async exportCsv(data: {
    region_ids?: string[];
    metrics?: string[];
    start_date?: string;
    end_date?: string;
    include_metadata?: boolean;
  }): Promise<ExportResponse> {
    const response = await this.client.post<ExportResponse>('/exports/csv', data);
    return response.data;
  }

  async exportAnimation(data: AnimationRequest): Promise<ExportResponse> {
    const response = await this.client.post<ExportResponse>('/exports/animation', data);
    return response.data;
  }

  async getExportStatus(id: string): Promise<ExportResponse> {
    const response = await this.client.get<ExportResponse>(`/exports/${id}/status`);
    return response.data;
  }

  getExportDownloadUrl(id: string): string {
    return `${API_BASE_URL}/exports/download/${id}`;
  }

  // Tiles
  getTileUrl(regionId: string, metric: string, date?: string): string {
    let url = `${API_BASE_URL}/tiles/${regionId}/${metric}/{z}/{x}/{y}.png`;
    if (date) {
      url += `?date=${date}`;
    }
    return url;
  }

  // US-wide pre-generated tiles (much faster, no region needed)
  // Supports both monthly (YYYY-MM) and daily (YYYY-MM-DD) formats
  // Daily granularity only available for nightlights and active_fire metrics
  // Version parameter busts browser cache when tile generation changes
  getUSTileUrl(metric: string, dateStr: string): string {
    const TILE_VERSION = 4; // Increment when tile generation/caching changes
    return `${API_BASE_URL}/tiles/us/${metric}/${dateStr}/{z}/{x}/{y}.png?v=${TILE_VERSION}`;
  }

  // Convert date (YYYY-MM-DD) to year-month (YYYY-MM)
  dateToYearMonth(date: string): string {
    return date.substring(0, 7);
  }

  // Get the appropriate date string for tiles based on metric and granularity
  getTileDateString(date: string, metric: string, granularity: 'daily' | 'monthly'): string {
    // Metrics that support daily granularity
    const dailyMetrics = ['nightlights', 'active_fire'];
    if (granularity === 'daily' && dailyMetrics.includes(metric)) {
      return date; // Return full YYYY-MM-DD
    }
    return this.dateToYearMonth(date); // Return YYYY-MM for monthly
  }

  async getRegionBounds(regionId: string): Promise<RegionBounds> {
    const response = await this.client.get<RegionBounds>(`/tiles/${regionId}/bounds`);
    return response.data;
  }

  // Check which US tiles are available
  async getUSAvailableTiles(): Promise<{
    status: string;
    metrics: Record<string, Array<{ year_month: string; tile_count: number }>>;
  }> {
    const response = await this.client.get('/tiles/us/available');
    return response.data;
  }

  // Auth
  async createApiKey(data: APIKeyCreate): Promise<APIKeyResponse> {
    const response = await this.client.post<APIKeyResponse>('/auth/keys', data);
    return response.data;
  }

  async listApiKeys(): Promise<{ keys: APIKeyResponse[]; total: number }> {
    const response = await this.client.get<{ keys: APIKeyResponse[]; total: number }>(
      '/auth/keys'
    );
    return response.data;
  }

  async revokeApiKey(id: string): Promise<void> {
    await this.client.delete(`/auth/keys/${id}`);
  }

  // Health
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await this.client.get<{ status: string; version: string }>('/health');
    return response.data;
  }
}

export const api = new APIClient();
export default api;
