import type { Granularity, MetricType } from '../types';

/** Canonical metric options for dropdowns and toggles across the app. */
export const METRIC_OPTIONS: { value: MetricType; label: string; color: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights', color: '#D97706' },
  { value: 'ndvi', label: 'NDVI (Vegetation)', color: '#059669' },
  { value: 'urban_density', label: 'Urban Density', color: '#7C3AED' },
  { value: 'parking', label: 'Parking Occupancy', color: '#0D9488' },
  { value: 'land_cover', label: 'Land Cover', color: '#9333EA' },
  { value: 'surface_water', label: 'Surface Water', color: '#2563EB' },
  { value: 'no2', label: 'NO\u2082 Pollution', color: '#6366F1' },
  { value: 'temperature', label: 'Temperature', color: '#EF4444' },
  { value: 'precipitation', label: 'Precipitation', color: '#3B82F6' },
  { value: 'aerosol', label: 'Aerosol Index', color: '#92400E' },
  { value: 'cropland', label: 'Cropland', color: '#16A34A' },
  { value: 'evapotranspiration', label: 'Evapotranspiration', color: '#0D9488' },
  { value: 'soil_moisture', label: 'Soil Moisture', color: '#7C3AED' },
  { value: 'impervious', label: 'Impervious Surface', color: '#6B7280' },
  { value: 'canopy_height', label: 'Canopy Height', color: '#15803D' },
];

/** All MetricType values as an array, derived from METRIC_OPTIONS. */
export const ALL_METRIC_TYPES: MetricType[] = METRIC_OPTIONS.map((o) => o.value);

/** Create an empty Record<MetricType, T> with a default value for each key. */
export function emptyMetricRecord<T>(defaultValue: T): Record<MetricType, T> {
  const record = {} as Record<MetricType, T>;
  for (const m of ALL_METRIC_TYPES) {
    record[m] = defaultValue;
  }
  return record;
}

// Keep in sync with backend metric definitions (backend/app/gee.py).
export const METRIC_DEFAULT_GRANULARITY: Record<MetricType, Granularity> = {
  ndvi: 'weekly',
  nightlights: 'monthly',
  urban_density: 'monthly',
  parking: 'weekly',
  land_cover: 'weekly',
  surface_water: 'monthly',
  no2: 'daily',
  temperature: 'daily',
  precipitation: 'daily',
  aerosol: 'daily',
  cropland: 'monthly',
  evapotranspiration: 'monthly',
  soil_moisture: 'weekly',
  impervious: 'monthly',
  canopy_height: 'monthly',
};

// Supported granularities per metric (backend/app/gee.py).
// Metrics with only one entry won't show a granularity toggle.
export const METRIC_SUPPORTED_GRANULARITIES: Record<MetricType, Granularity[]> = {
  ndvi: ['weekly', 'monthly'],
  nightlights: ['daily', 'monthly'],
  urban_density: ['monthly'],
  parking: ['weekly', 'monthly'],
  land_cover: ['weekly', 'monthly'],
  surface_water: ['monthly'],
  no2: ['daily', 'monthly'],
  temperature: ['daily', 'monthly'],
  precipitation: ['daily', 'monthly'],
  aerosol: ['daily', 'monthly'],
  cropland: ['monthly'],
  evapotranspiration: ['monthly'],
  soil_moisture: ['weekly', 'monthly'],
  impervious: ['monthly'],
  canopy_height: ['monthly'],
};

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
