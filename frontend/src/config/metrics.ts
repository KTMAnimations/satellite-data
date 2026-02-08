import type { Granularity, MetricType } from '../types';

interface MetricMetaBase {
  label: string;
  color: string;
  valueRange: [number, number];
  description?: string;
}

const METRIC_METADATA_BASE: Record<MetricType, MetricMetaBase> = {
  ndvi: { label: 'NDVI', color: '#059669', valueRange: [-1, 1], description: 'Vegetation greenness index' },
  nightlights: { label: 'Nighttime Lights', color: '#D97706', valueRange: [0, 100], description: 'Nighttime luminosity proxy' },
  urban_density: { label: 'Urban Density', color: '#7C3AED', valueRange: [0, 1], description: 'Built-surface fraction proxy' },
  parking: { label: 'Parking Occupancy', color: '#0D9488', valueRange: [0, 1], description: 'Impervious lot activity proxy' },
  land_cover: { label: 'Land Cover (Built-up)', color: '#9333EA', valueRange: [0, 1], description: 'Dynamic World built probability' },
  surface_water: { label: 'Surface Water', color: '#2563EB', valueRange: [0, 1], description: 'Open water fraction proxy' },
  no2: { label: 'NO2', color: '#6366F1', valueRange: [0, 0.0002], description: 'Tropospheric NO2 column' },
  temperature: { label: 'Temperature', color: '#EF4444', valueRange: [-30, 45], description: '2m air temperature' },
  precipitation: { label: 'Precipitation', color: '#3B82F6', valueRange: [0, 500], description: 'Accumulated precipitation' },
  aerosol: { label: 'Aerosol Index', color: '#92400E', valueRange: [-2, 5], description: 'Aerosol loading proxy' },
  cropland: { label: 'Cropland', color: '#16A34A', valueRange: [0, 1], description: 'Cropland fraction proxy' },
  evapotranspiration: { label: 'Evapotranspiration', color: '#0D9488', valueRange: [0, 40], description: 'Evapotranspiration amount' },
  soil_moisture: { label: 'Soil Moisture', color: '#7C3AED', valueRange: [0, 0.5], description: 'Surface soil moisture' },
  impervious: { label: 'Impervious Surface', color: '#6B7280', valueRange: [0, 1], description: 'Urbanized impervious fraction' },
  canopy_height: { label: 'Canopy Height', color: '#15803D', valueRange: [0, 60], description: 'Canopy height proxy' },

  evi: { label: 'EVI', color: '#2E7D32', valueRange: [-1, 1] },
  ndre: { label: 'NDRE', color: '#388E3C', valueRange: [-1, 1] },
  ndmi: { label: 'NDMI', color: '#1D4ED8', valueRange: [-1, 1] },
  ndwi: { label: 'NDWI', color: '#0EA5E9', valueRange: [-1, 1] },
  mndwi: { label: 'MNDWI', color: '#0284C7', valueRange: [-1, 1] },
  savi: { label: 'SAVI', color: '#65A30D', valueRange: [-1, 1] },
  bsi: { label: 'Bare Soil Index', color: '#B45309', valueRange: [-1, 1] },
  nbr: { label: 'NBR', color: '#EA580C', valueRange: [-1, 1] },
  dnbr: { label: 'dNBR', color: '#DC2626', valueRange: [-2, 2] },
  gci: { label: 'GCI', color: '#16A34A', valueRange: [-1, 10] },
  ndsi: { label: 'NDSI', color: '#60A5FA', valueRange: [-1, 1] },

  s1_vv: { label: 'Sentinel-1 VV', color: '#475569', valueRange: [-25, 5] },
  s1_vh: { label: 'Sentinel-1 VH', color: '#334155', valueRange: [-35, 0] },
  s1_vh_vv_ratio: { label: 'Sentinel-1 VH/VV Ratio', color: '#0F172A', valueRange: [-20, 5] },
  s1_rvi: { label: 'Sentinel-1 RVI', color: '#047857', valueRange: [0, 4] },

  lst_day: { label: 'LST Day', color: '#EF4444', valueRange: [-30, 60] },
  lst_night: { label: 'LST Night', color: '#F97316', valueRange: [-40, 40] },
  lst_diurnal_range: { label: 'LST Diurnal Range', color: '#FB923C', valueRange: [0, 30] },
  albedo_black_sky: { label: 'Black-sky Albedo', color: '#6B7280', valueRange: [0, 1] },
  albedo_white_sky: { label: 'White-sky Albedo', color: '#9CA3AF', valueRange: [0, 1] },
  par: { label: 'PAR', color: '#F59E0B', valueRange: [0, 25] },

  lai: { label: 'LAI', color: '#22C55E', valueRange: [0, 10] },
  fpar: { label: 'FPAR', color: '#84CC16', valueRange: [0, 1] },
  gpp: { label: 'GPP', color: '#16A34A', valueRange: [0, 10] },
  npp: { label: 'NPP', color: '#15803D', valueRange: [0, 10] },
  biomass_agb_carbon: { label: 'Biomass AGB Carbon', color: '#166534', valueRange: [0, 400] },
  biomass_bgb_carbon: { label: 'Biomass BGB Carbon', color: '#14532D', valueRange: [0, 200] },
  gedi_agbd: { label: 'GEDI AGBD', color: '#065F46', valueRange: [0, 500] },

  active_fire_temp: { label: 'Active Fire Temperature', color: '#DC2626', valueRange: [250, 500] },
  active_fire_confidence: { label: 'Active Fire Confidence', color: '#B91C1C', valueRange: [0, 100] },
  burned_area_date: { label: 'Burn Date', color: '#9A3412', valueRange: [1, 366] },
  burned_area_fraction: { label: 'Burned Area Fraction', color: '#C2410C', valueRange: [0, 1] },

  treecover_2000: { label: 'Tree Cover 2000', color: '#15803D', valueRange: [0, 100] },
  forest_loss_year: { label: 'Forest Loss Year', color: '#92400E', valueRange: [2001, 2025] },
  forest_gain: { label: 'Forest Gain', color: '#22C55E', valueRange: [0, 1] },
  forest_loss_fraction: { label: 'Forest Loss Fraction', color: '#D97706', valueRange: [0, 1] },

  snow_cover: { label: 'Snow Cover', color: '#60A5FA', valueRange: [0, 100] },
  fractional_snow_cover: { label: 'Fractional Snow Cover', color: '#93C5FD', valueRange: [0, 100] },
  snow_albedo: { label: 'Snow Albedo', color: '#BFDBFE', valueRange: [0, 100] },
  snow_cover_8day: { label: 'Snow Cover 8-day', color: '#DBEAFE', valueRange: [0, 100] },

  tws_anomaly: { label: 'TWS Anomaly', color: '#2563EB', valueRange: [-50, 50] },
  flood_max_extent: { label: 'Flood Max Extent', color: '#1D4ED8', valueRange: [0, 1] },
  flood_duration_days: { label: 'Flood Duration', color: '#1E40AF', valueRange: [0, 365] },
  flood_observation_quality: { label: 'Flood Observation Quality', color: '#475569', valueRange: [0, 100] },

  drought_pdsi: { label: 'PDSI', color: '#B45309', valueRange: [-10, 10] },
  vpd: { label: 'VPD', color: '#F97316', valueRange: [0, 5] },
  runoff: { label: 'Runoff', color: '#0EA5E9', valueRange: [0, 500] },
  clim_water_deficit: { label: 'Climatic Water Deficit', color: '#EA580C', valueRange: [0, 500] },

  elevation: { label: 'Elevation', color: '#7C2D12', valueRange: [-500, 9000] },
  slope: { label: 'Slope', color: '#A16207', valueRange: [0, 90] },
  aspect: { label: 'Aspect', color: '#0F766E', valueRange: [0, 360] },
  terrain_ruggedness: { label: 'Terrain Ruggedness', color: '#78350F', valueRange: [0, 1000] },

  soil_organic_carbon: { label: 'Soil Organic Carbon', color: '#92400E', valueRange: [0, 200] },
  soil_ph: { label: 'Soil pH', color: '#B45309', valueRange: [3, 10] },
  soil_sand_fraction: { label: 'Soil Sand Fraction', color: '#D97706', valueRange: [0, 100] },
  soil_field_capacity: { label: 'Soil Field Capacity', color: '#0369A1', valueRange: [0, 100] },

  population_count: { label: 'Population Count', color: '#7C3AED', valueRange: [0, 1000] },
  population_density: { label: 'Population Density', color: '#6D28D9', valueRange: [0, 30000] },
  building_presence: { label: 'Building Presence', color: '#4B5563', valueRange: [0, 1] },
  building_height: { label: 'Building Height', color: '#374151', valueRange: [0, 100] },
  building_count_proxy: { label: 'Building Count Proxy', color: '#1F2937', valueRange: [0, 100] },
  building_footprints_density: { label: 'Building Footprint Density', color: '#111827', valueRange: [0, 1] },
  travel_time_to_cities: { label: 'Travel Time to Cities', color: '#9333EA', valueRange: [0, 720] },
  human_modification: { label: 'Human Modification', color: '#A855F7', valueRange: [0, 1] },

  co: { label: 'CO', color: '#4338CA', valueRange: [0, 0.1] },
  so2: { label: 'SO2', color: '#4F46E5', valueRange: [0, 0.001] },
  o3: { label: 'O3', color: '#6366F1', valueRange: [0, 0.2] },
  hcho: { label: 'HCHO', color: '#818CF8', valueRange: [0, 0.001] },
  ch4: { label: 'CH4', color: '#A78BFA', valueRange: [1600, 2000] },
  pm25: { label: 'PM2.5', color: '#7F1D1D', valueRange: [0, 200] },

  sst: { label: 'Sea Surface Temperature', color: '#0284C7', valueRange: [-2, 35] },
  ocean_chlorophyll: { label: 'Ocean Chlorophyll', color: '#0EA5E9', valueRange: [0, 50] },
  ocean_poc: { label: 'Ocean POC', color: '#06B6D4', valueRange: [0, 2000] },
  bathymetry: { label: 'Bathymetry', color: '#1E3A8A', valueRange: [-11000, 9000] },
};

const WEEKLY_MONTHLY_METRICS = new Set<MetricType>([
  'ndvi',
  'parking',
  'land_cover',
  'soil_moisture',
  'evi',
  'ndre',
  'ndmi',
  'ndwi',
  'mndwi',
  'savi',
  'bsi',
  'nbr',
  'gci',
  'ndsi',
  's1_vv',
  's1_vh',
  's1_vh_vv_ratio',
  's1_rvi',
]);

const DAILY_MONTHLY_METRICS = new Set<MetricType>([
  'nightlights',
  'no2',
  'temperature',
  'precipitation',
  'aerosol',
  'lst_day',
  'lst_night',
  'lst_diurnal_range',
  'albedo_black_sky',
  'albedo_white_sky',
  'par',
  'active_fire_temp',
  'active_fire_confidence',
  'snow_cover',
  'fractional_snow_cover',
  'snow_albedo',
  'co',
  'so2',
  'o3',
  'hcho',
  'ch4',
  'pm25',
  'sst',
]);

const DAILY_DEFAULT_METRICS = new Set<MetricType>([
  'nightlights',
  'no2',
  'temperature',
  'precipitation',
  'aerosol',
  'active_fire_temp',
  'active_fire_confidence',
  'snow_cover',
  'fractional_snow_cover',
  'snow_albedo',
  'co',
  'so2',
  'o3',
  'hcho',
  'ch4',
  'pm25',
  'sst',
]);

function defaultGranularity(metric: MetricType): Granularity {
  if (DAILY_DEFAULT_METRICS.has(metric)) return 'daily';
  if (WEEKLY_MONTHLY_METRICS.has(metric)) return 'weekly';
  return 'monthly';
}

function supportedGranularities(metric: MetricType): Granularity[] {
  if (DAILY_MONTHLY_METRICS.has(metric)) return ['daily', 'monthly'];
  if (WEEKLY_MONTHLY_METRICS.has(metric)) return ['weekly', 'monthly'];
  return ['monthly'];
}

/** Canonical metric options for dropdowns and toggles across the app. */
export const METRIC_OPTIONS: { value: MetricType; label: string; color: string }[] =
  (Object.entries(METRIC_METADATA_BASE) as [MetricType, MetricMetaBase][]).map(([value, meta]) => ({
    value,
    label: meta.label,
    color: meta.color,
  }));

/** All MetricType values as an array, derived from METRIC_OPTIONS. */
export const ALL_METRIC_TYPES: MetricType[] = METRIC_OPTIONS.map((o) => o.value);

export const METRIC_LABELS: Record<MetricType, string> =
  Object.fromEntries((Object.entries(METRIC_METADATA_BASE) as [MetricType, MetricMetaBase][]).map(([id, meta]) => [id, meta.label])) as Record<MetricType, string>;

export const METRIC_COLORS: Record<MetricType, string> =
  Object.fromEntries((Object.entries(METRIC_METADATA_BASE) as [MetricType, MetricMetaBase][]).map(([id, meta]) => [id, meta.color])) as Record<MetricType, string>;

export const METRIC_DESCRIPTIONS: Record<MetricType, string | undefined> =
  Object.fromEntries((Object.entries(METRIC_METADATA_BASE) as [MetricType, MetricMetaBase][]).map(([id, meta]) => [id, meta.description])) as Record<MetricType, string | undefined>;

export const METRIC_VALUE_RANGES: Record<MetricType, [number, number]> =
  Object.fromEntries((Object.entries(METRIC_METADATA_BASE) as [MetricType, MetricMetaBase][]).map(([id, meta]) => [id, meta.valueRange])) as Record<MetricType, [number, number]>;

export function getMetricLabel(metric: MetricType): string {
  return METRIC_LABELS[metric] ?? metric;
}

export function getMetricColor(metric: MetricType): string {
  return METRIC_COLORS[metric] ?? '#64748B';
}

export function getMetricDescription(metric: MetricType): string {
  return METRIC_DESCRIPTIONS[metric] ?? 'Satellite-derived metric';
}

/** Create an empty Record<MetricType, T> with a default value for each key. */
export function emptyMetricRecord<T>(defaultValue: T): Record<MetricType, T> {
  const record = {} as Record<MetricType, T>;
  for (const m of ALL_METRIC_TYPES) {
    record[m] = defaultValue;
  }
  return record;
}

// Keep in sync with backend metric definitions (backend/app/gee.py).
export const METRIC_DEFAULT_GRANULARITY: Record<MetricType, Granularity> =
  Object.fromEntries(ALL_METRIC_TYPES.map((metric) => [metric, defaultGranularity(metric)])) as Record<MetricType, Granularity>;

// Supported granularities per metric (backend/app/gee.py).
// Metrics with only one entry won't show a granularity toggle.
export const METRIC_SUPPORTED_GRANULARITIES: Record<MetricType, Granularity[]> =
  Object.fromEntries(ALL_METRIC_TYPES.map((metric) => [metric, supportedGranularities(metric)])) as Record<MetricType, Granularity[]>;

// Keep in sync with backend Settings.max_timeseries_points (backend/app/settings.py).
export const METRICS_MAX_TIMESERIES_POINTS_DEFAULT = 2000;

const GRANULARITY_ORDER: Record<Granularity, number> = {
  daily: 0,
  weekly: 1,
  monthly: 2,
};

function toDateOnly(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function estimateBucketCount(start: Date, end: Date, granularity: Granularity): number {
  const startDate = toDateOnly(start);
  const endDate = toDateOnly(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return 0;
  if (startDate.getTime() > endDate.getTime()) return 0;

  const msPerDay = 1000 * 60 * 60 * 24;

  if (granularity === 'daily') {
    const diffDays = Math.floor((endDate.getTime() - startDate.getTime()) / msPerDay);
    return diffDays + 1;
  }

  if (granularity === 'weekly') {
    const diffDays = Math.floor((endDate.getTime() - startDate.getTime()) / msPerDay);
    return Math.floor(diffDays / 7) + 1;
  }

  // monthly: mirror backend bucket_starts behavior (start at first day of month)
  let current = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
  let count = 0;
  while (current.getTime() <= endDate.getTime()) {
    count += 1;
    current = new Date(current.getFullYear(), current.getMonth() + 1, 1);
  }
  return count;
}

/**
 * Returns an automatic/default granularity for a metric + date range.
 *
 * - Picks the least granular supported option (monthly > weekly > daily)
 * - Falls back to a finer supported option only if the estimated bucket count
 *   would exceed the backend time-series limit.
 */
export function getRecommendedGranularity(
  metric: MetricType,
  dateRange: { start: Date; end: Date },
  maxPoints: number = METRICS_MAX_TIMESERIES_POINTS_DEFAULT
): Granularity {
  const supported = METRIC_SUPPORTED_GRANULARITIES[metric] ?? [];
  const candidates = [...supported].sort(
    (a, b) => GRANULARITY_ORDER[b] - GRANULARITY_ORDER[a]
  );

  for (const candidate of candidates) {
    if (estimateBucketCount(dateRange.start, dateRange.end, candidate) <= maxPoints) {
      return candidate;
    }
  }

  return candidates[0] ?? METRIC_DEFAULT_GRANULARITY[metric];
}
