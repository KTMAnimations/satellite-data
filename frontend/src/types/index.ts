// Region types
export interface Region {
  id: string;
  name: string;
  description: string | null;
  geometry: GeoJSONPolygon;
  type: 'predefined' | 'custom';
  country: string | null;
  state_province: string | null;
  category: 'major_city' | 'megacity' | 'migration_hotspot' | null;
  created_at: string;
  updated_at: string;
}

export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface RegionListResponse {
  regions: Region[];
  total: number;
  page: number;
  page_size: number;
}

// Metrics types
export type MetricType =
  // Original metrics
  | 'ndvi'
  | 'nightlights'
  // Phase 1: Core datasets
  | 'surface_water'
  // Phase 2: Air quality & weather
  | 'no2'
  | 'temperature'
  | 'precipitation'
  | 'aerosol'
  // Phase 3: Agriculture
  | 'cropland'
  | 'evapotranspiration'
  | 'soil_moisture'
  // Phase 4: Historical & specialized
  | 'impervious'
  | 'canopy_height'
  | 'forest_loss_year'
  | 'snow_cover'
  | 'travel_time_to_cities';

export type Granularity = 'daily' | 'weekly' | 'monthly';

export interface MetricDataPoint {
  date: string;
  value: number;
}

export interface MetricData {
  unit: string;
  data: MetricDataPoint[];
}

export interface SeasonalAverage {
  // Original metrics
  ndvi: number | null;
  nightlights: number | null;
  // Phase 1: Core datasets
  surface_water: number | null;
  // Phase 2: Air quality & weather
  no2: number | null;
  temperature: number | null;
  precipitation: number | null;
  aerosol: number | null;
  // Phase 3: Agriculture
  cropland: number | null;
  evapotranspiration: number | null;
  soil_moisture: number | null;
  // Phase 4: Historical & specialized
  impervious: number | null;
  canopy_height: number | null;
  forest_loss_year: number | null;
  snow_cover: number | null;
  travel_time_to_cities: number | null;
}

export interface SeasonalSummary {
  winter_avg: SeasonalAverage;
  summer_avg: SeasonalAverage;
  change_pct: SeasonalAverage;
}

export interface MetricsResponse {
  region_id: string;
  region_name: string;
  metrics: Partial<Record<MetricType, MetricData>>;
  seasonal_summary: SeasonalSummary | null;
}

// Compare types
export interface CompareRequest {
  region_id: string;
  period_a_start: string;
  period_a_end: string;
  period_b_start: string;
  period_b_end: string;
  metrics?: MetricType[];
}

export interface PeriodSummary {
  start_date: string;
  end_date: string;
  averages: Record<string, number>;
  observation_count: number;
}

export interface CompareResponse {
  region_id: string;
  region_name: string;
  period_a: PeriodSummary;
  period_b: PeriodSummary;
  change: Record<string, number>;
  change_absolute: Record<string, number>;
}

// Tiles
export interface TileTemplateResponse {
  metric: MetricType;
  date_bucket: string;
  granularity: Granularity;
  tile_url: string;
  attribution: string | null;
  min: number;
  max: number;
  palette: string[];
  opacity: number;
}

export interface TileCacheClearResponse {
  metric: MetricType;
  cache_enabled: boolean;
  deleted_files: number;
  deleted_bytes: number;
}

// Export types
export interface ExportRequest {
  region_id: string;
  format: 'pdf';
  start_date?: string;
  end_date?: string;
  metrics?: MetricType[];
  include_charts?: boolean;
  include_maps?: boolean;
  title?: string;
  description?: string;
}

export interface ExportResponse {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  format: string;
  progress?: number;
  message?: string | null;
  download_url: string | null;
  file_size: number | null;
  created_at: string;
  completed_at: string | null;
  error?: string | null;
}

export interface AnimationRequest {
  region_id: string;
  metric: MetricType;
  format: 'gif';
  include_basemap?: boolean;
  overlay_opacity?: number;
  start_date: string;
  end_date: string;
  frame_duration_ms?: number;
  width?: number;
  height?: number;
}

// App state types
export interface DateRange {
  start: Date;
  end: Date;
}

export interface MapState {
  center: [number, number];
  zoom: number;
  contextRegionId: string | null;
}

// Presets
export interface PresetRegion {
  name: string;
  region_id: string | null;
}

export interface PresetDateRange {
  start_date: string;
  end_date: string;
}

export interface PresetComparePeriod {
  label: string | null;
  start_date: string;
  end_date: string;
}

export interface PresetCompare {
  period_a: PresetComparePeriod;
  period_b: PresetComparePeriod;
}

export interface Preset {
  id: string;
  name: string;
  description: string;
  category: string | null;
  regions: PresetRegion[];
  metrics: MetricType[];
  date_range: PresetDateRange | null;
  compare: PresetCompare | null;
  methodology_notes: string | null;
}

export interface PresetListResponse {
  presets: Preset[];
}

// Admin / telemetry
export interface AdminIpSummary {
  ip_address: string;
  first_seen_at: string;
  last_seen_at: string;
  instance_count: number;
  event_count: number;
}

export interface AdminIpListResponse {
  ips: AdminIpSummary[];
  total: number;
}

export interface AdminInstanceSummary {
  instance_id: string;
  device_id: string | null;
  user_agent: string | null;
  accept_language: string | null;
  first_seen_at: string;
  last_seen_at: string;
  last_path: string | null;
  event_count: number;
}

export interface AdminIpDetailResponse {
  ip: AdminIpSummary;
  instances: AdminInstanceSummary[];
}

export interface AdminInstanceDetailResponse {
  instance_id: string;
  device_id: string | null;
  ip_address: string;
  user_agent: string | null;
  accept_language: string | null;
  meta: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  last_path: string | null;
  total_events: number;
  event_type_counts: Record<string, number>;
  distinct_paths: number;
}

export interface AdminTelemetryEvent {
  id: number;
  event_type: string;
  client_ts_ms: number | null;
  received_at: string;
  path: string | null;
  data: Record<string, unknown> | null;
}

export interface AdminInstanceEventsResponse {
  instance_id: string;
  events: AdminTelemetryEvent[];
  total: number;
}
