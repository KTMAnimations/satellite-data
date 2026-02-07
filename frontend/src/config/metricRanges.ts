import type { MetricType } from '../types';

// Keep in sync with backend metric definitions (backend/app/gee.py).
export const METRIC_VALUE_RANGES: Record<MetricType, [number, number]> = {
  ndvi: [-1.0, 1.0],
  nightlights: [0.0, 100.0],
  urban_density: [0.0, 1.0],
  parking: [0.0, 1.0],
  land_cover: [0.0, 1.0],
  surface_water: [0.0, 1.0],
  no2: [0.0, 0.0002],
  temperature: [-30.0, 45.0],
  precipitation: [0.0, 500.0],
  aerosol: [-2.0, 5.0],
  cropland: [0.0, 1.0],
  evapotranspiration: [0.0, 20.0],
  soil_moisture: [0.0, 0.5],
  impervious: [0.0, 1.0],
  canopy_height: [0.0, 60.0],
};
