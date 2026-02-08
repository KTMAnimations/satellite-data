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
  // Vegetation / optical indices
  | 'evi'
  | 'ndre'
  | 'ndmi'
  | 'ndwi'
  | 'mndwi'
  | 'savi'
  | 'bsi'
  | 'nbr'
  | 'dnbr'
  | 'gci'
  | 'ndsi'
  // Radar
  | 's1_vv'
  | 's1_vh'
  | 's1_vh_vv_ratio'
  | 's1_rvi'
  // Surface energy / temperature
  | 'lst_day'
  | 'lst_night'
  | 'lst_diurnal_range'
  | 'albedo_black_sky'
  | 'albedo_white_sky'
  | 'par'
  // Productivity / biomass
  | 'lai'
  | 'fpar'
  | 'gpp'
  | 'npp'
  | 'biomass_agb_carbon'
  | 'biomass_bgb_carbon'
  | 'gedi_agbd'
  // Fire
  | 'active_fire_temp'
  | 'active_fire_confidence'
  | 'burned_area_date'
  | 'burned_area_fraction'
  // Forest change
  | 'treecover_2000'
  | 'forest_loss_year'
  | 'forest_gain'
  | 'forest_loss_fraction'
  // Snow / cryosphere
  | 'snow_cover'
  | 'fractional_snow_cover'
  | 'snow_albedo'
  | 'snow_cover_8day'
  // Water / flood / drought
  | 'tws_anomaly'
  | 'flood_max_extent'
  | 'flood_duration_days'
  | 'flood_observation_quality'
  | 'drought_pdsi'
  | 'vpd'
  | 'runoff'
  | 'clim_water_deficit'
  // Terrain
  | 'elevation'
  | 'slope'
  | 'aspect'
  | 'terrain_ruggedness'
  // Soils
  | 'soil_organic_carbon'
  | 'soil_ph'
  | 'soil_sand_fraction'
  | 'soil_field_capacity'
  // Human systems
  | 'population_count'
  | 'population_density'
  | 'building_presence'
  | 'building_height'
  | 'building_count_proxy'
  | 'building_footprints_density'
  | 'travel_time_to_cities'
  | 'human_modification'
  // Air quality
  | 'co'
  | 'so2'
  | 'o3'
  | 'hcho'
  | 'ch4'
  | 'pm25'
  // Oceans
  | 'sst'
  | 'ocean_chlorophyll'
  | 'ocean_poc'
  | 'bathymetry';

export type Granularity = 'daily' | 'weekly' | 'monthly';

export interface MetricDataPoint {
  date: string;
  value: number;
}

export interface MetricData {
  unit: string;
  data: MetricDataPoint[];
}

export type SeasonalAverage = Partial<Record<MetricType, number | null>>;

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
