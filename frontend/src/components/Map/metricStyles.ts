import type { MetricType } from '../../types';
import { METRIC_VALUE_RANGES } from '../../config/metricRanges';

// Colormaps matching backend - converted to RGB hex
export const COLORMAPS: Record<MetricType, string[]> = {
  nightlights: ['#e8c36a', '#efd084', '#f3db9d', '#f7e5b6', '#faedcb', '#fdf3dc', '#fef8ea', '#fffbf2', '#fffdf8', '#ffffff'],
  ndvi: ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
  urban_density: ['#ffffe5', '#fff7bc', '#fee391', '#fec44f', '#fe9929', '#ec7014', '#cc4c02', '#993404', '#662506', '#331203'],
  parking: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b', '#03132b'],
  land_cover: ['#f7f4f9', '#e7e1ef', '#d4b9da', '#c994c7', '#ba6eb4', '#aa4da0', '#98318b', '#7a0177', '#5c015e', '#3f003c'],
  surface_water: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
  no2: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  temperature: ['#053061', '#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#fddbc7', '#f4a582', '#d6604d', '#b2182b', '#67001f'],
  precipitation: ['#ffffff', '#f0f9e8', '#ccebc5', '#a8ddb5', '#7bccc4', '#4eb3d3', '#2b8cbe', '#0868ac', '#084081', '#252556'],
  aerosol: ['#ffffff', '#fdf5e6', '#fce0c5', '#f9c496', '#f4a267', '#dd8541', '#b2672d', '#8a4a1c', '#64320e', '#321405'],
  cropland: ['#ffffb2', '#fed976', '#feb24c', '#fd8d3c', '#f03b20', '#bd0026', '#228b22', '#32cd32', '#90ee90', '#ffff00'],
  evapotranspiration: ['#a6611a', '#bf812d', '#dfc27d', '#e6d8b2', '#f5f5dc', '#c7eae5', '#80cdc1', '#35978f', '#01665e', '#003c30'],
  soil_moisture: ['#8b4513', '#a0522d', '#bc8f5f', '#d2b48c', '#f5deb3', '#add8e6', '#87ceeb', '#4682b4', '#4169e1', '#00008b'],
  impervious: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1a1a1a', '#000000'],
  canopy_height: ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#006d2c', '#004d1c', '#00280f'],
  co_column_density: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  so2_column_density: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  o3_total_column: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  tropospheric_ozone_column: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  methane_mixing_ratio: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  formaldehyde_column: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  aerosol_layer_height: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  cloud_fraction: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
  cloud_top_height: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
  aod_550: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  active_fire_hotspots: ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026', '#4d0018'],
  burned_area_fraction: ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026', '#4d0018'],
  burn_day_of_year: ['#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026', '#4d0018'],
  river_flood_depth_rp100: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
  water_recurrence: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
  snow_cover: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#6a51a3', '#54278f', '#3f007d'],
  snow_albedo: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#6a51a3', '#54278f', '#3f007d'],
  terrestrial_water_storage: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#a50026'],
  drought_pdsi: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#a50026'],
  climatic_water_deficit: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#a50026'],
  runoff: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
  snow_water_equivalent: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#6a51a3', '#54278f', '#3f007d'],
  vegetation_water_deficit: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#a50026'],
  wind_speed_climate: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b', '#041a3d'],
  evi_modis: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  lai: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  fpar: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  gpp_8day: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  npp_annual: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  phenology_greenup: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  phenology_senescence: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  landsat_ndwi_8day: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
  landsat_evi_8day: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  forest_loss_year: ['#ffffe5', '#f7fcb9', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#006837', '#004529', '#002a1f'],
  forest_loss_fraction: ['#ffffe5', '#f7fcb9', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#006837', '#004529', '#002a1f'],
  tree_cover_2000: ['#ffffe5', '#f7fcb9', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#006837', '#004529', '#002a1f'],
  forest_gain: ['#ffffe5', '#f7fcb9', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#006837', '#004529', '#002a1f'],
  population_count_ghsl: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  population_count_worldpop: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  population_density_gpw: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  built_height: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  built_volume_total: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  built_volume_nonres: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  degree_of_urbanization: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  radar_backscatter_vv: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  radar_backscatter_vh: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  elevation_dem30: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  elevation_srtm: ['#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696', '#737373', '#525252', '#363636', '#1f1f1f', '#000000'],
  dw_trees: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  dw_grass: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  dw_flooded_vegetation: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  dw_shrub_scrub: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  dw_bare: ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#c7eae5', '#80cdc1', '#35978f', '#1f6d6f', '#01665e', '#003c30'],
  dw_snow_ice: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#6a51a3', '#54278f', '#3f007d'],
  wind_speed_10m: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b', '#041a3d'],
  relative_humidity_2m: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b', '#041a3d'],
  surface_pressure: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b', '#041a3d'],
  solar_radiation_down: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b', '#041a3d'],
  snow_depth_era5: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#6a51a3', '#54278f', '#3f007d'],
  runoff_era5: ['#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9', '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360'],
};

// Value ranges for each metric
export const VALUE_RANGES: Record<MetricType, [number, number]> = METRIC_VALUE_RANGES;

export function interpolateColor(colors: string[], t: number): string {
  // Clamp t to [0, 1]
  t = Math.max(0, Math.min(1, t));

  const idx = t * (colors.length - 1);
  const idxLow = Math.floor(idx);
  const idxHigh = Math.min(idxLow + 1, colors.length - 1);
  const blend = idx - idxLow;

  const colorLow = colors[idxLow];
  const colorHigh = colors[idxHigh];

  // Parse hex colors
  const rLow = parseInt(colorLow.slice(1, 3), 16);
  const gLow = parseInt(colorLow.slice(3, 5), 16);
  const bLow = parseInt(colorLow.slice(5, 7), 16);

  const rHigh = parseInt(colorHigh.slice(1, 3), 16);
  const gHigh = parseInt(colorHigh.slice(3, 5), 16);
  const bHigh = parseInt(colorHigh.slice(5, 7), 16);

  // Interpolate
  const r = Math.round(rLow * (1 - blend) + rHigh * blend);
  const g = Math.round(gLow * (1 - blend) + gHigh * blend);
  const b = Math.round(bLow * (1 - blend) + bHigh * blend);

  return `rgb(${r}, ${g}, ${b})`;
}
