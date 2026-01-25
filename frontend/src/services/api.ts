import axios, { AxiosInstance, AxiosError } from 'axios';
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

// Demo data for when backend is unavailable
const DEMO_REGIONS: Region[] = [
  {
    id: 'demo-phoenix',
    name: 'Phoenix, AZ',
    description: 'Phoenix metropolitan area - one of the fastest growing US cities',
    type: 'predefined',
    category: 'Major Cities',
    country: 'USA',
    state_province: 'Arizona',
    bounds: { minLat: 33.29, maxLat: 33.92, minLon: -112.33, maxLon: -111.93 },
    center: { lat: 33.45, lon: -112.07 },
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'demo-miami',
    name: 'Miami, FL',
    description: 'Miami-Dade County - major snowbird destination',
    type: 'predefined',
    category: 'Migration Hotspots',
    country: 'USA',
    state_province: 'Florida',
    bounds: { minLat: 25.71, maxLat: 25.86, minLon: -80.32, maxLon: -80.13 },
    center: { lat: 25.76, lon: -80.19 },
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'demo-newyork',
    name: 'New York, NY',
    description: 'New York City metropolitan area',
    type: 'predefined',
    category: 'Megacities',
    country: 'USA',
    state_province: 'New York',
    bounds: { minLat: 40.49, maxLat: 40.92, minLon: -74.26, maxLon: -73.70 },
    center: { lat: 40.71, lon: -74.01 },
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'demo-lasvegas',
    name: 'Las Vegas, NV',
    description: 'Las Vegas metropolitan area - tourism-driven economy',
    type: 'predefined',
    category: 'Migration Hotspots',
    country: 'USA',
    state_province: 'Nevada',
    bounds: { minLat: 36.00, maxLat: 36.30, minLon: -115.35, maxLon: -115.00 },
    center: { lat: 36.17, lon: -115.14 },
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'demo-tampa',
    name: 'Tampa, FL',
    description: 'Tampa Bay area - major Sun Belt destination',
    type: 'predefined',
    category: 'Migration Hotspots',
    country: 'USA',
    state_province: 'Florida',
    bounds: { minLat: 27.82, maxLat: 28.08, minLon: -82.62, maxLon: -82.32 },
    center: { lat: 27.95, lon: -82.46 },
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'demo-austin',
    name: 'Austin, TX',
    description: 'Austin metropolitan area - college town with tech growth',
    type: 'predefined',
    category: 'Major Cities',
    country: 'USA',
    state_province: 'Texas',
    bounds: { minLat: 30.10, maxLat: 30.52, minLon: -97.94, maxLon: -97.56 },
    center: { lat: 30.27, lon: -97.74 },
    created_at: '2024-01-01T00:00:00Z',
  },
];

// Generate demo metrics data
function generateDemoMetrics(regionId: string): MetricsResponse {
  const months = [];
  for (let year = 2022; year <= 2024; year++) {
    for (let month = 1; month <= 12; month++) {
      months.push(`${year}-${String(month).padStart(2, '0')}-01`);
    }
  }

  const region = DEMO_REGIONS.find(r => r.id === regionId);

  return {
    region_id: regionId,
    region_name: region?.name || 'Unknown',
    metrics: {
      nightlights: {
        unit: 'nW/cm²/sr',
        data: months.map((date, i) => ({
          date,
          value: 35 + Math.sin(i / 6 * Math.PI) * 15 + Math.random() * 5,
        })),
      },
      ndvi: {
        unit: 'index',
        data: months.map((date, i) => ({
          date,
          value: 0.2 + Math.sin((i + 3) / 6 * Math.PI) * 0.15 + Math.random() * 0.05,
        })),
      },
      urban_density: {
        unit: 'ratio',
        data: months.map((date, i) => ({
          date,
          value: 0.65 + (i / months.length) * 0.1 + Math.random() * 0.02,
        })),
      },
      parking: {
        unit: '%',
        data: months.map((date, i) => ({
          date,
          value: 50 + Math.sin(i / 6 * Math.PI) * 20 + Math.random() * 10,
        })),
      },
    },
    seasonal_summary: {
      winter_avg: {
        nightlights: 48.5,
        ndvi: 0.15,
        urban_density: 0.72,
        parking: 68,
      },
      summer_avg: {
        nightlights: 35.2,
        ndvi: 0.32,
        urban_density: 0.71,
        parking: 52,
      },
      change_pct: {
        nightlights: 37.8,
        ndvi: -53.1,
        urban_density: 1.4,
        parking: 30.8,
      },
    },
  };
}

class APIClient {
  private client: AxiosInstance;
  private apiKey: string | null = null;
  private useDemoData: boolean = false;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 5000,
    });

    // Add API key to requests if available
    this.client.interceptors.request.use((config) => {
      if (this.apiKey) {
        config.headers['X-API-Key'] = this.apiKey;
      }
      return config;
    });

    // Check if backend is available
    this.checkBackendAvailability();
  }

  private async checkBackendAvailability() {
    try {
      await this.client.get('/health', { timeout: 2000 });
      this.useDemoData = false;
      console.log('Backend connected');
    } catch {
      this.useDemoData = true;
      console.log('Backend unavailable, using demo data');
    }
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
    if (this.useDemoData) {
      let filteredRegions = [...DEMO_REGIONS];

      if (params?.type) {
        filteredRegions = filteredRegions.filter(r => r.type === params.type);
      }
      if (params?.category) {
        filteredRegions = filteredRegions.filter(r => r.category === params.category);
      }
      if (params?.search) {
        const search = params.search.toLowerCase();
        filteredRegions = filteredRegions.filter(r =>
          r.name.toLowerCase().includes(search) ||
          r.description?.toLowerCase().includes(search)
        );
      }

      return {
        regions: filteredRegions,
        total: filteredRegions.length,
        page: params?.page || 1,
        page_size: params?.page_size || 20,
      };
    }

    try {
      const response = await this.client.get<RegionListResponse>('/regions', { params });
      return response.data;
    } catch (error) {
      this.useDemoData = true;
      return this.listRegions(params);
    }
  }

  async getRegion(id: string): Promise<Region> {
    if (this.useDemoData) {
      const region = DEMO_REGIONS.find(r => r.id === id);
      if (region) return region;
      throw new Error('Region not found');
    }

    try {
      const response = await this.client.get<Region>(`/regions/${id}`);
      return response.data;
    } catch (error) {
      this.useDemoData = true;
      return this.getRegion(id);
    }
  }

  async createRegion(data: {
    name: string;
    description?: string;
    geometry: GeoJSONPolygon;
    country?: string;
    state_province?: string;
  }): Promise<Region> {
    if (this.useDemoData) {
      // In demo mode, create a temporary region
      const newRegion: Region = {
        id: `custom-${Date.now()}`,
        name: data.name,
        description: data.description,
        type: 'custom',
        category: 'Custom',
        country: data.country,
        state_province: data.state_province,
        bounds: { minLat: 0, maxLat: 0, minLon: 0, maxLon: 0 },
        center: { lat: 0, lon: 0 },
        created_at: new Date().toISOString(),
      };
      DEMO_REGIONS.push(newRegion);
      return newRegion;
    }

    const response = await this.client.post<Region>('/regions', data);
    return response.data;
  }

  async deleteRegion(id: string): Promise<void> {
    if (this.useDemoData) {
      const index = DEMO_REGIONS.findIndex(r => r.id === id);
      if (index > -1) {
        DEMO_REGIONS.splice(index, 1);
      }
      return;
    }

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
    if (this.useDemoData) {
      return generateDemoMetrics(regionId);
    }

    try {
      const response = await this.client.get<MetricsResponse>(`/metrics/${regionId}`, {
        params,
      });
      return response.data;
    } catch (error) {
      this.useDemoData = true;
      return this.getMetrics(regionId, params);
    }
  }

  // Analysis
  async requestAnalysis(data: AnalysisRequest): Promise<AnalysisStatus> {
    if (this.useDemoData) {
      return {
        id: `analysis-${Date.now()}`,
        status: 'completed',
        progress: 100,
        created_at: new Date().toISOString(),
      };
    }

    const response = await this.client.post<AnalysisStatus>('/analysis', data);
    return response.data;
  }

  async getAnalysisStatus(id: string): Promise<AnalysisStatus> {
    if (this.useDemoData) {
      return {
        id,
        status: 'completed',
        progress: 100,
        created_at: new Date().toISOString(),
      };
    }

    const response = await this.client.get<AnalysisStatus>(`/analysis/${id}/status`);
    return response.data;
  }

  async getRegionAnalyses(
    regionId: string,
    analysisType?: string
  ): Promise<AnalysisResponse[]> {
    if (this.useDemoData) {
      return [];
    }

    const response = await this.client.get<AnalysisResponse[]>(`/analysis/${regionId}`, {
      params: { analysis_type: analysisType },
    });
    return response.data;
  }

  async comparePeriods(data: CompareRequest): Promise<CompareResponse> {
    if (this.useDemoData) {
      return {
        region_id: data.region_id,
        period_a: { start: data.period_a_start, end: data.period_a_end },
        period_b: { start: data.period_b_start, end: data.period_b_end },
        comparison: {
          nightlights: { period_a_avg: 48.5, period_b_avg: 35.2, change_pct: 37.8 },
          ndvi: { period_a_avg: 0.15, period_b_avg: 0.32, change_pct: -53.1 },
          urban_density: { period_a_avg: 0.72, period_b_avg: 0.71, change_pct: 1.4 },
          parking: { period_a_avg: 68, period_b_avg: 52, change_pct: 30.8 },
        },
      };
    }

    const response = await this.client.post<CompareResponse>('/analysis/compare', data);
    return response.data;
  }

  // Exports
  async exportPdf(data: ExportRequest): Promise<ExportResponse> {
    if (this.useDemoData) {
      return {
        id: `export-${Date.now()}`,
        format: 'pdf',
        status: 'completed',
        created_at: new Date().toISOString(),
        download_url: '#',
      };
    }

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
    if (this.useDemoData) {
      return {
        id: `export-${Date.now()}`,
        format: 'csv',
        status: 'completed',
        created_at: new Date().toISOString(),
        download_url: '#',
      };
    }

    const response = await this.client.post<ExportResponse>('/exports/csv', data);
    return response.data;
  }

  async exportAnimation(data: AnimationRequest): Promise<ExportResponse> {
    if (this.useDemoData) {
      return {
        id: `export-${Date.now()}`,
        format: 'animation',
        status: 'completed',
        created_at: new Date().toISOString(),
        download_url: '#',
      };
    }

    const response = await this.client.post<ExportResponse>('/exports/animation', data);
    return response.data;
  }

  async getExportStatus(id: string): Promise<ExportResponse> {
    if (this.useDemoData) {
      return {
        id,
        format: 'pdf',
        status: 'completed',
        created_at: new Date().toISOString(),
        download_url: '#',
      };
    }

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

  async getRegionBounds(regionId: string): Promise<RegionBounds> {
    if (this.useDemoData) {
      const region = DEMO_REGIONS.find(r => r.id === regionId);
      if (region) {
        return region.bounds;
      }
      return { minLat: 33.29, maxLat: 33.92, minLon: -112.33, maxLon: -111.93 };
    }

    const response = await this.client.get<RegionBounds>(`/tiles/${regionId}/bounds`);
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
    if (this.useDemoData) {
      return { status: 'demo', version: '0.1.0' };
    }

    const response = await this.client.get<{ status: string; version: string }>('/health');
    return response.data;
  }

  // Getter for demo mode status
  isDemoMode(): boolean {
    return this.useDemoData;
  }
}

export const api = new APIClient();
export default api;
