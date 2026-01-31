import type { Granularity, MetricType } from '../types';

// Keep in sync with backend metric definitions (backend/app/gee.py).
export const METRIC_DEFAULT_GRANULARITY: Record<MetricType, Granularity> = {
  ndvi: 'weekly',
  nightlights: 'monthly',
  urban_density: 'monthly',
  parking: 'weekly',
  land_cover: 'weekly',
  surface_water: 'monthly',
  active_fire: 'daily',
  no2: 'daily',
  temperature: 'daily',
  precipitation: 'daily',
  aerosol: 'daily',
  cropland: 'monthly',
  evapotranspiration: 'monthly',
  soil_moisture: 'weekly',
  impervious: 'monthly',
  fire_historical: 'monthly',
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
  active_fire: ['daily', 'monthly'],
  no2: ['daily', 'monthly'],
  temperature: ['daily', 'monthly'],
  precipitation: ['daily', 'monthly'],
  aerosol: ['daily', 'monthly'],
  cropland: ['monthly'],
  evapotranspiration: ['monthly'],
  soil_moisture: ['weekly', 'monthly'],
  impervious: ['monthly'],
  fire_historical: ['monthly'],
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
 * - Picks the most granular supported option (daily > weekly > monthly)
 * - Falls back to a coarser supported option if the estimated bucket count
 *   would exceed the backend time-series limit.
 */
export function getRecommendedGranularity(
  metric: MetricType,
  dateRange: { start: Date; end: Date },
  maxPoints: number = METRICS_MAX_TIMESERIES_POINTS_DEFAULT
): Granularity {
  const supported = METRIC_SUPPORTED_GRANULARITIES[metric] ?? [];
  const candidates = [...supported].sort(
    (a, b) => GRANULARITY_ORDER[a] - GRANULARITY_ORDER[b]
  );

  for (const candidate of candidates) {
    if (estimateBucketCount(dateRange.start, dateRange.end, candidate) <= maxPoints) {
      return candidate;
    }
  }

  return candidates[candidates.length - 1] ?? METRIC_DEFAULT_GRANULARITY[metric];
}
