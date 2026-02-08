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
  | 'nightlights'
  | 'ndvi'
  | 'urban_density'
  | 'parking'
  | 'land_cover'
  | 'surface_water'
  | 'no2'
  | 'temperature'
  | 'precipitation'
  | 'aerosol'
  | 'cropland'
  | 'evapotranspiration'
  | 'soil_moisture'
  | 'impervious'
  | 'canopy_height'
  | 'co_column_density'
  | 'so2_column_density'
  | 'o3_total_column'
  | 'tropospheric_ozone_column'
  | 'methane_mixing_ratio'
  | 'formaldehyde_column'
  | 'aerosol_layer_height'
  | 'cloud_fraction'
  | 'cloud_top_height'
  | 'aod_550'
  | 'active_fire_hotspots'
  | 'burned_area_fraction'
  | 'burn_day_of_year'
  | 'river_flood_depth_rp100'
  | 'water_recurrence'
  | 'snow_cover'
  | 'snow_albedo'
  | 'terrestrial_water_storage'
  | 'drought_pdsi'
  | 'climatic_water_deficit'
  | 'runoff'
  | 'snow_water_equivalent'
  | 'vegetation_water_deficit'
  | 'wind_speed_climate'
  | 'evi_modis'
  | 'lai'
  | 'fpar'
  | 'gpp_8day'
  | 'npp_annual'
  | 'phenology_greenup'
  | 'phenology_senescence'
  | 'landsat_ndwi_8day'
  | 'landsat_evi_8day'
  | 'forest_loss_year'
  | 'forest_loss_fraction'
  | 'tree_cover_2000'
  | 'forest_gain'
  | 'population_count_ghsl'
  | 'population_count_worldpop'
  | 'population_density_gpw'
  | 'built_height'
  | 'built_volume_total'
  | 'built_volume_nonres'
  | 'degree_of_urbanization'
  | 'radar_backscatter_vv'
  | 'radar_backscatter_vh'
  | 'elevation_dem30'
  | 'elevation_srtm'
  | 'dw_trees'
  | 'dw_grass'
  | 'dw_flooded_vegetation'
  | 'dw_shrub_scrub'
  | 'dw_bare'
  | 'dw_snow_ice'
  | 'wind_speed_10m'
  | 'relative_humidity_2m'
  | 'surface_pressure'
  | 'solar_radiation_down'
  | 'snow_depth_era5'
  | 'runoff_era5'

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
  nightlights: number | null;
  ndvi: number | null;
  urban_density: number | null;
  parking: number | null;
  land_cover: number | null;
  surface_water: number | null;
  no2: number | null;
  temperature: number | null;
  precipitation: number | null;
  aerosol: number | null;
  cropland: number | null;
  evapotranspiration: number | null;
  soil_moisture: number | null;
  impervious: number | null;
  canopy_height: number | null;
  co_column_density: number | null;
  so2_column_density: number | null;
  o3_total_column: number | null;
  tropospheric_ozone_column: number | null;
  methane_mixing_ratio: number | null;
  formaldehyde_column: number | null;
  aerosol_layer_height: number | null;
  cloud_fraction: number | null;
  cloud_top_height: number | null;
  aod_550: number | null;
  active_fire_hotspots: number | null;
  burned_area_fraction: number | null;
  burn_day_of_year: number | null;
  river_flood_depth_rp100: number | null;
  water_recurrence: number | null;
  snow_cover: number | null;
  snow_albedo: number | null;
  terrestrial_water_storage: number | null;
  drought_pdsi: number | null;
  climatic_water_deficit: number | null;
  runoff: number | null;
  snow_water_equivalent: number | null;
  vegetation_water_deficit: number | null;
  wind_speed_climate: number | null;
  evi_modis: number | null;
  lai: number | null;
  fpar: number | null;
  gpp_8day: number | null;
  npp_annual: number | null;
  phenology_greenup: number | null;
  phenology_senescence: number | null;
  landsat_ndwi_8day: number | null;
  landsat_evi_8day: number | null;
  forest_loss_year: number | null;
  forest_loss_fraction: number | null;
  tree_cover_2000: number | null;
  forest_gain: number | null;
  population_count_ghsl: number | null;
  population_count_worldpop: number | null;
  population_density_gpw: number | null;
  built_height: number | null;
  built_volume_total: number | null;
  built_volume_nonres: number | null;
  degree_of_urbanization: number | null;
  radar_backscatter_vv: number | null;
  radar_backscatter_vh: number | null;
  elevation_dem30: number | null;
  elevation_srtm: number | null;
  dw_trees: number | null;
  dw_grass: number | null;
  dw_flooded_vegetation: number | null;
  dw_shrub_scrub: number | null;
  dw_bare: number | null;
  dw_snow_ice: number | null;
  wind_speed_10m: number | null;
  relative_humidity_2m: number | null;
  surface_pressure: number | null;
  solar_radiation_down: number | null;
  snow_depth_era5: number | null;
  runoff_era5: number | null;
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
