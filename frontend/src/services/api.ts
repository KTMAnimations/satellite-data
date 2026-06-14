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
  TileCacheClearResponse,
  AdminIpDetailResponse,
  AdminIpListResponse,
  AdminInstanceDetailResponse,
  AdminInstanceEventsResponse,
  GeeKeyStatus,
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

  private adminHeaders(token: string | undefined): Record<string, string> | undefined {
    const t = (token ?? '').trim();
    if (!t) return undefined;
    return { Authorization: `Bearer ${t}` };
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

  async clearTileCacheMetric(metric: MetricType, options?: RequestOptions): Promise<TileCacheClearResponse> {
    const response = await this.client.delete<TileCacheClearResponse>(`/tiles/cache/${metric}`, {
      signal: options?.signal,
    });
    return response.data;
  }

  // Admin
  async adminListIps(
    params?: { limit?: number; offset?: number },
    token?: string,
    options?: RequestOptions
  ): Promise<AdminIpListResponse> {
    const response = await this.client.get<AdminIpListResponse>('/admin/ips', {
      params,
      headers: this.adminHeaders(token),
      signal: options?.signal,
    });
    return response.data;
  }

  async adminGetIpDetail(ipAddress: string, token?: string, options?: RequestOptions): Promise<AdminIpDetailResponse> {
    const response = await this.client.get<AdminIpDetailResponse>(`/admin/ips/${encodeURIComponent(ipAddress)}`, {
      headers: this.adminHeaders(token),
      signal: options?.signal,
    });
    return response.data;
  }

  async adminGetInstanceDetail(
    instanceId: string,
    token?: string,
    options?: RequestOptions
  ): Promise<AdminInstanceDetailResponse> {
    const response = await this.client.get<AdminInstanceDetailResponse>(`/admin/instances/${instanceId}`, {
      headers: this.adminHeaders(token),
      signal: options?.signal,
    });
    return response.data;
  }

  async adminListInstanceEvents(
    instanceId: string,
    params?: { limit?: number; offset?: number },
    token?: string,
    options?: RequestOptions
  ): Promise<AdminInstanceEventsResponse> {
    const response = await this.client.get<AdminInstanceEventsResponse>(`/admin/instances/${instanceId}/events`, {
      params,
      headers: this.adminHeaders(token),
      signal: options?.signal,
    });
    return response.data;
  }

  async adminGetGeeKeyStatus(token?: string, options?: RequestOptions): Promise<GeeKeyStatus> {
    const response = await this.client.get<GeeKeyStatus>('/admin/credentials/gee', {
      headers: this.adminHeaders(token),
      signal: options?.signal,
    });
    return response.data;
  }

  async adminUpdateGeeKey(keyJson: string, token?: string, options?: RequestOptions): Promise<GeeKeyStatus> {
    const response = await this.client.post<GeeKeyStatus>(
      '/admin/credentials/gee',
      { key_json: keyJson },
      { headers: this.adminHeaders(token), signal: options?.signal },
    );
    return response.data;
  }
}

export const api = new APIClient();
export default api;
