import type { Granularity, MetricType } from '../types';

// Keep in sync with backend metric defaults (backend/app/gee.py).
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

