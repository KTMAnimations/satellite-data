import axios, { AxiosInstance } from 'axios';
import type {
  Region,
  RegionListResponse,
  Preset,
  PresetListResponse,
  MetricsResponse,
  CompareRequest,
  CompareResponse,
  ExportRequest,
  ExportResponse,
  AnimationRequest,
  GeoJSONPolygon,
  Granularity,
  MetricType,
  TileTemplateResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

type RequestOptions = {
  signal?: AbortSignal;
};

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
      paramsSerializer: { indexes: null },
    });
  }

  // Regions
  async listRegions(params?: {
    page?: number;
    page_size?: number;
    type?: string;
    category?: string;
    country?: string;
    search?: string;
  }, options?: RequestOptions): Promise<RegionListResponse> {
    const response = await this.client.get<RegionListResponse>('/regions', { params, signal: options?.signal });
    return response.data;
  }

  async getRegion(id: string, options?: RequestOptions): Promise<Region> {
    const response = await this.client.get<Region>(`/regions/${id}`, { signal: options?.signal });
    return response.data;
  }

  async createRegion(data: {
    name: string;
    description?: string;
    geometry: GeoJSONPolygon;
    country?: string;
    state_province?: string;
  }, options?: RequestOptions): Promise<Region> {
    const response = await this.client.post<Region>('/regions', data, { signal: options?.signal });
    return response.data;
  }

  async deleteRegion(id: string, options?: RequestOptions): Promise<void> {
    await this.client.delete(`/regions/${id}`, { signal: options?.signal });
  }

  // Presets
  async listPresets(options?: RequestOptions): Promise<PresetListResponse> {
    const response = await this.client.get<PresetListResponse>('/presets', { signal: options?.signal });
    return response.data;
  }

  async getPreset(id: string, options?: RequestOptions): Promise<Preset> {
    const response = await this.client.get<Preset>(`/presets/${id}`, { signal: options?.signal });
    return response.data;
  }

  // Metrics
  async getMetrics(
    regionId: string,
    params?: {
      start_date?: string;
      end_date?: string;
      metrics?: MetricType[];
      granularity?: Granularity;
    },
    options?: RequestOptions
  ): Promise<MetricsResponse> {
    const response = await this.client.get<MetricsResponse>(`/metrics/${regionId}`, {
      params,
      signal: options?.signal,
    });
    return response.data;
  }

  async comparePeriods(data: CompareRequest, options?: RequestOptions): Promise<CompareResponse> {
    const response = await this.client.post<CompareResponse>('/analysis/compare', data, { signal: options?.signal });
    return response.data;
  }

  // Exports
  async exportPdf(data: ExportRequest, options?: RequestOptions): Promise<ExportResponse> {
    const response = await this.client.post<ExportResponse>('/exports/pdf', data, { signal: options?.signal });
    return response.data;
  }

  async exportCsv(data: {
    region_ids?: string[];
    metrics?: MetricType[];
    start_date?: string;
    end_date?: string;
    include_metadata?: boolean;
  }, options?: RequestOptions): Promise<ExportResponse> {
    const response = await this.client.post<ExportResponse>('/exports/csv', data, { signal: options?.signal });
    return response.data;
  }

  async exportAnimation(data: AnimationRequest, options?: RequestOptions): Promise<ExportResponse> {
    const response = await this.client.post<ExportResponse>('/exports/animation', data, { signal: options?.signal });
    return response.data;
  }

  async getExportStatus(id: string, options?: RequestOptions): Promise<ExportResponse> {
    const response = await this.client.get<ExportResponse>(`/exports/${id}/status`, { signal: options?.signal });
    return response.data;
  }

  getExportDownloadUrl(id: string): string {
    return `${API_BASE_URL}/exports/download/${id}`;
  }

  // Tiles (Earth Engine URL templates)
  async getTileTemplate(params: {
    metric: MetricType;
    date_bucket: string;
    granularity: Granularity;
    opacity?: number;
  }, options?: RequestOptions): Promise<TileTemplateResponse> {
    const response = await this.client.get<TileTemplateResponse>('/tiles/template', { params, signal: options?.signal });
    return response.data;
  }
}

export const api = new APIClient();
export default api;
