import type { Granularity, MetricType } from '../types';

/** Canonical metric options for dropdowns and toggles across the app. */
export const METRIC_OPTIONS: { value: MetricType; label: string; color: string; description: string; unit: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights', color: '#D97706', description: 'Urban activity proxy (VIIRS)', unit: 'nW/cm^2/sr' },
  { value: 'ndvi', label: 'NDVI', color: '#059669', description: 'Vegetation index', unit: 'index (-1 to 1)' },
  { value: 'urban_density', label: 'Urban Density', color: '#7C3AED', description: 'Built-up area fraction (GHSL)', unit: 'ratio (0 to 1)' },
  { value: 'parking', label: 'Parking Occupancy', color: '#0D9488', description: 'NDBI-based occupancy proxy', unit: 'index (0 to 1)' },
  { value: 'land_cover', label: 'Land Cover', color: '#9333EA', description: 'Dynamic World built probability', unit: 'probability (0 to 1)' },
  { value: 'surface_water', label: 'Surface Water', color: '#2563EB', description: 'JRC monthly water extent', unit: 'ratio (0 to 1)' },
  { value: 'no2', label: 'NO2', color: '#6366F1', description: 'Tropospheric nitrogen dioxide', unit: 'mol/m^2' },
  { value: 'temperature', label: 'Temperature', color: '#EF4444', description: '2m air temperature', unit: 'degC' },
  { value: 'precipitation', label: 'Precipitation', color: '#3B82F6', description: 'Rainfall / precipitation sum', unit: 'mm' },
  { value: 'aerosol', label: 'Aerosol Index', color: '#92400E', description: 'Absorbing aerosol index', unit: 'index' },
  { value: 'cropland', label: 'Cropland', color: '#16A34A', description: 'Cropland probability/fraction', unit: 'ratio (0 to 1)' },
  { value: 'evapotranspiration', label: 'Evapotranspiration', color: '#0D9488', description: 'Water flux from land/vegetation', unit: 'mm' },
  { value: 'soil_moisture', label: 'Soil Moisture', color: '#7C3AED', description: 'Volumetric soil moisture', unit: 'm^3/m^3' },
  { value: 'impervious', label: 'Impervious Surface', color: '#6B7280', description: 'Urban impervious footprint', unit: 'ratio (0 to 1)' },
  { value: 'canopy_height', label: 'Canopy Height', color: '#15803D', description: 'Tree canopy height', unit: 'm' },
  { value: 'co_column_density', label: 'CO Column Density', color: '#4F46E5', description: 'Sentinel-5P carbon monoxide column', unit: 'mol/m^2' },
  { value: 'so2_column_density', label: 'SO2 Column Density', color: '#7C3AED', description: 'Sentinel-5P sulfur dioxide column', unit: 'mol/m^2' },
  { value: 'o3_total_column', label: 'O3 Total Column', color: '#2563EB', description: 'Sentinel-5P total ozone column', unit: 'mol/m^2' },
  { value: 'tropospheric_ozone_column', label: 'Tropospheric Ozone', color: '#1D4ED8', description: 'Sentinel-5P tropospheric ozone', unit: 'mol/m^2' },
  { value: 'methane_mixing_ratio', label: 'Methane Mixing Ratio', color: '#0EA5E9', description: 'Sentinel-5P methane mixing ratio', unit: 'mol fraction' },
  { value: 'formaldehyde_column', label: 'Formaldehyde Column', color: '#0F766E', description: 'Sentinel-5P formaldehyde column', unit: 'mol/m^2' },
  { value: 'aerosol_layer_height', label: 'Aerosol Layer Height', color: '#B45309', description: 'Sentinel-5P aerosol layer height', unit: 'm' },
  { value: 'cloud_fraction', label: 'Cloud Fraction', color: '#1D4ED8', description: 'Sentinel-5P cloud fraction', unit: 'fraction (0 to 1)' },
  { value: 'cloud_top_height', label: 'Cloud Top Height', color: '#2563EB', description: 'Sentinel-5P cloud-top height', unit: 'm' },
  { value: 'aod_550', label: 'AOD 550nm', color: '#92400E', description: 'MODIS MAIAC aerosol optical depth at 550nm', unit: 'aod' },
  { value: 'active_fire_hotspots', label: 'Active Fire Hotspots', color: '#DC2626', description: 'FIRMS active fire hotspots', unit: 'hotspots per pixel' },
  { value: 'burned_area_fraction', label: 'Burned Area Fraction', color: '#B91C1C', description: 'MODIS monthly burned-area mask', unit: 'ratio (0 to 1)' },
  { value: 'burn_day_of_year', label: 'Burn Day Of Year', color: '#EA580C', description: 'MODIS burn timing day-of-year', unit: 'day of year' },
  { value: 'river_flood_depth_rp100', label: 'Flood Depth RP100', color: '#1E40AF', description: 'JRC flood depth return period 100y', unit: 'm' },
  { value: 'water_recurrence', label: 'Water Recurrence', color: '#1D4ED8', description: 'JRC monthly water recurrence', unit: 'percent' },
  { value: 'snow_cover', label: 'Snow Cover', color: '#3B82F6', description: 'MODIS snow cover fraction', unit: 'percent' },
  { value: 'snow_albedo', label: 'Snow Albedo', color: '#2563EB', description: 'MODIS snow albedo', unit: 'percent' },
  { value: 'terrestrial_water_storage', label: 'Terrestrial Water Storage', color: '#0284C7', description: 'GRACE terrestrial water storage anomaly', unit: 'cm' },
  { value: 'drought_pdsi', label: 'Drought PDSI', color: '#B91C1C', description: 'TerraClimate Palmer drought severity index', unit: 'pdsi' },
  { value: 'climatic_water_deficit', label: 'Climatic Water Deficit', color: '#A16207', description: 'TerraClimate climate water deficit', unit: 'mm' },
  { value: 'runoff', label: 'Runoff', color: '#0369A1', description: 'TerraClimate runoff', unit: 'mm' },
  { value: 'snow_water_equivalent', label: 'Snow Water Equivalent', color: '#1D4ED8', description: 'TerraClimate SWE', unit: 'mm' },
  { value: 'vegetation_water_deficit', label: 'Vegetation Water Deficit', color: '#B45309', description: 'TerraClimate vapor pressure deficit', unit: 'kPa' },
  { value: 'wind_speed_climate', label: 'Wind Speed Climate', color: '#2563EB', description: 'TerraClimate wind speed', unit: 'm/s' },
  { value: 'evi_modis', label: 'EVI MODIS', color: '#059669', description: 'MODIS enhanced vegetation index', unit: 'index' },
  { value: 'lai', label: 'Leaf Area Index', color: '#0F766E', description: 'MODIS leaf area index', unit: 'm^2/m^2' },
  { value: 'fpar', label: 'FPAR', color: '#15803D', description: 'MODIS fraction of absorbed PAR', unit: 'fraction (0 to 1)' },
  { value: 'gpp_8day', label: 'GPP 8-Day', color: '#16A34A', description: 'MODIS gross primary productivity', unit: 'kg*C/m^2' },
  { value: 'npp_annual', label: 'NPP Annual', color: '#166534', description: 'MODIS net primary productivity', unit: 'kg*C/m^2' },
  { value: 'phenology_greenup', label: 'Phenology Greenup', color: '#22C55E', description: 'MODIS greenup timing', unit: 'day of year' },
  { value: 'phenology_senescence', label: 'Phenology Senescence', color: '#84CC16', description: 'MODIS senescence timing', unit: 'day of year' },
  { value: 'landsat_ndwi_8day', label: 'Landsat NDWI 8-Day', color: '#0EA5E9', description: 'Landsat 8-day NDWI composite', unit: 'index (-1 to 1)' },
  { value: 'landsat_evi_8day', label: 'Landsat EVI 8-Day', color: '#10B981', description: 'Landsat 8-day EVI composite', unit: 'index (-1 to 1)' },
  { value: 'forest_loss_year', label: 'Forest Loss Year', color: '#B45309', description: 'Hansen forest-loss year', unit: 'year' },
  { value: 'forest_loss_fraction', label: 'Forest Loss Fraction', color: '#991B1B', description: 'Hansen cumulative loss fraction', unit: 'ratio (0 to 1)' },
  { value: 'tree_cover_2000', label: 'Tree Cover 2000', color: '#15803D', description: 'Hansen baseline tree cover', unit: 'percent' },
  { value: 'forest_gain', label: 'Forest Gain', color: '#16A34A', description: 'Hansen forest gain mask', unit: 'ratio (0 to 1)' },
  { value: 'population_count_ghsl', label: 'Population Count GHSL', color: '#7C3AED', description: 'GHSL population count', unit: 'people per cell' },
  { value: 'population_count_worldpop', label: 'Population Count WorldPop', color: '#8B5CF6', description: 'WorldPop population count', unit: 'people per cell' },
  { value: 'population_density_gpw', label: 'Population Density GPW', color: '#6D28D9', description: 'GPW population density', unit: 'people/km^2' },
  { value: 'built_height', label: 'Built Height', color: '#4B5563', description: 'GHSL average building height', unit: 'm' },
  { value: 'built_volume_total', label: 'Built Volume Total', color: '#374151', description: 'GHSL total building volume', unit: 'm^3' },
  { value: 'built_volume_nonres', label: 'Built Volume Non-Residential', color: '#111827', description: 'GHSL non-residential building volume', unit: 'm^3' },
  { value: 'degree_of_urbanization', label: 'Degree Of Urbanization', color: '#6B7280', description: 'GHSL degree of urbanization class', unit: 'class code' },
  { value: 'radar_backscatter_vv', label: 'Radar Backscatter VV', color: '#0F766E', description: 'Sentinel-1 VV backscatter', unit: 'dB' },
  { value: 'radar_backscatter_vh', label: 'Radar Backscatter VH', color: '#115E59', description: 'Sentinel-1 VH backscatter', unit: 'dB' },
  { value: 'elevation_dem30', label: 'Elevation DEM30', color: '#4B5563', description: 'Copernicus 30m DEM elevation', unit: 'm' },
  { value: 'elevation_srtm', label: 'Elevation SRTM', color: '#6B7280', description: 'SRTM elevation fallback', unit: 'm' },
  { value: 'dw_trees', label: 'Dynamic World Trees', color: '#15803D', description: 'Dynamic World trees probability', unit: 'probability (0 to 1)' },
  { value: 'dw_grass', label: 'Dynamic World Grass', color: '#22C55E', description: 'Dynamic World grass probability', unit: 'probability (0 to 1)' },
  { value: 'dw_flooded_vegetation', label: 'Dynamic World Flooded Vegetation', color: '#0D9488', description: 'Dynamic World flooded vegetation probability', unit: 'probability (0 to 1)' },
  { value: 'dw_shrub_scrub', label: 'Dynamic World Shrub Scrub', color: '#65A30D', description: 'Dynamic World shrub/scrub probability', unit: 'probability (0 to 1)' },
  { value: 'dw_bare', label: 'Dynamic World Bare', color: '#A16207', description: 'Dynamic World bare-ground probability', unit: 'probability (0 to 1)' },
  { value: 'dw_snow_ice', label: 'Dynamic World Snow Ice', color: '#1D4ED8', description: 'Dynamic World snow/ice probability', unit: 'probability (0 to 1)' },
  { value: 'wind_speed_10m', label: 'Wind Speed 10m', color: '#2563EB', description: 'ERA5-Land 10m wind speed', unit: 'm/s' },
  { value: 'relative_humidity_2m', label: 'Relative Humidity 2m', color: '#0891B2', description: 'ERA5-Land relative humidity', unit: 'percent' },
  { value: 'surface_pressure', label: 'Surface Pressure', color: '#1E40AF', description: 'ERA5-Land surface pressure', unit: 'hPa' },
  { value: 'solar_radiation_down', label: 'Solar Radiation Down', color: '#D97706', description: 'ERA5-Land downward shortwave radiation', unit: 'MJ/m^2' },
  { value: 'snow_depth_era5', label: 'Snow Depth ERA5', color: '#1D4ED8', description: 'ERA5-Land snow depth', unit: 'm' },
  { value: 'runoff_era5', label: 'Runoff ERA5', color: '#0369A1', description: 'ERA5-Land runoff', unit: 'mm' },
];

/** All MetricType values as an array, derived from METRIC_OPTIONS. */
export const ALL_METRIC_TYPES: MetricType[] = METRIC_OPTIONS.map((o) => o.value);

export const METRIC_LABELS: Record<MetricType, string> = Object.fromEntries(
  METRIC_OPTIONS.map((o) => [o.value, o.label])
) as Record<MetricType, string>;

export const METRIC_COLORS: Record<MetricType, string> = Object.fromEntries(
  METRIC_OPTIONS.map((o) => [o.value, o.color])
) as Record<MetricType, string>;

export const METRIC_DESCRIPTIONS: Record<MetricType, string> = Object.fromEntries(
  METRIC_OPTIONS.map((o) => [o.value, o.description])
) as Record<MetricType, string>;

export const METRIC_UNITS: Record<MetricType, string> = Object.fromEntries(
  METRIC_OPTIONS.map((o) => [o.value, o.unit])
) as Record<MetricType, string>;

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
  nightlights: 'monthly',
  ndvi: 'weekly',
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
  co_column_density: 'daily',
  so2_column_density: 'daily',
  o3_total_column: 'daily',
  tropospheric_ozone_column: 'daily',
  methane_mixing_ratio: 'daily',
  formaldehyde_column: 'daily',
  aerosol_layer_height: 'daily',
  cloud_fraction: 'daily',
  cloud_top_height: 'daily',
  aod_550: 'daily',
  active_fire_hotspots: 'daily',
  burned_area_fraction: 'monthly',
  burn_day_of_year: 'monthly',
  river_flood_depth_rp100: 'monthly',
  water_recurrence: 'monthly',
  snow_cover: 'daily',
  snow_albedo: 'daily',
  terrestrial_water_storage: 'monthly',
  drought_pdsi: 'monthly',
  climatic_water_deficit: 'monthly',
  runoff: 'monthly',
  snow_water_equivalent: 'monthly',
  vegetation_water_deficit: 'monthly',
  wind_speed_climate: 'monthly',
  evi_modis: 'weekly',
  lai: 'weekly',
  fpar: 'weekly',
  gpp_8day: 'weekly',
  npp_annual: 'monthly',
  phenology_greenup: 'monthly',
  phenology_senescence: 'monthly',
  landsat_ndwi_8day: 'weekly',
  landsat_evi_8day: 'weekly',
  forest_loss_year: 'monthly',
  forest_loss_fraction: 'monthly',
  tree_cover_2000: 'monthly',
  forest_gain: 'monthly',
  population_count_ghsl: 'monthly',
  population_count_worldpop: 'monthly',
  population_density_gpw: 'monthly',
  built_height: 'monthly',
  built_volume_total: 'monthly',
  built_volume_nonres: 'monthly',
  degree_of_urbanization: 'monthly',
  radar_backscatter_vv: 'weekly',
  radar_backscatter_vh: 'weekly',
  elevation_dem30: 'monthly',
  elevation_srtm: 'monthly',
  dw_trees: 'weekly',
  dw_grass: 'weekly',
  dw_flooded_vegetation: 'weekly',
  dw_shrub_scrub: 'weekly',
  dw_bare: 'weekly',
  dw_snow_ice: 'weekly',
  wind_speed_10m: 'daily',
  relative_humidity_2m: 'daily',
  surface_pressure: 'daily',
  solar_radiation_down: 'daily',
  snow_depth_era5: 'daily',
  runoff_era5: 'daily',
};

// Supported granularities per metric (backend/app/gee.py).
// Metrics with only one entry won't show a granularity toggle.
export const METRIC_SUPPORTED_GRANULARITIES: Record<MetricType, Granularity[]> = {
  nightlights: ['daily', 'monthly'],
  ndvi: ['weekly', 'monthly'],
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
  co_column_density: ['daily', 'monthly'],
  so2_column_density: ['daily', 'monthly'],
  o3_total_column: ['daily', 'monthly'],
  tropospheric_ozone_column: ['daily', 'monthly'],
  methane_mixing_ratio: ['daily', 'monthly'],
  formaldehyde_column: ['daily', 'monthly'],
  aerosol_layer_height: ['daily', 'monthly'],
  cloud_fraction: ['daily', 'monthly'],
  cloud_top_height: ['daily', 'monthly'],
  aod_550: ['daily', 'monthly'],
  active_fire_hotspots: ['daily', 'monthly'],
  burned_area_fraction: ['monthly'],
  burn_day_of_year: ['monthly'],
  river_flood_depth_rp100: ['monthly'],
  water_recurrence: ['monthly'],
  snow_cover: ['daily', 'monthly'],
  snow_albedo: ['daily', 'monthly'],
  terrestrial_water_storage: ['monthly'],
  drought_pdsi: ['monthly'],
  climatic_water_deficit: ['monthly'],
  runoff: ['monthly'],
  snow_water_equivalent: ['monthly'],
  vegetation_water_deficit: ['monthly'],
  wind_speed_climate: ['monthly'],
  evi_modis: ['weekly', 'monthly'],
  lai: ['weekly', 'monthly'],
  fpar: ['weekly', 'monthly'],
  gpp_8day: ['weekly', 'monthly'],
  npp_annual: ['monthly'],
  phenology_greenup: ['monthly'],
  phenology_senescence: ['monthly'],
  landsat_ndwi_8day: ['weekly', 'monthly'],
  landsat_evi_8day: ['weekly', 'monthly'],
  forest_loss_year: ['monthly'],
  forest_loss_fraction: ['monthly'],
  tree_cover_2000: ['monthly'],
  forest_gain: ['monthly'],
  population_count_ghsl: ['monthly'],
  population_count_worldpop: ['monthly'],
  population_density_gpw: ['monthly'],
  built_height: ['monthly'],
  built_volume_total: ['monthly'],
  built_volume_nonres: ['monthly'],
  degree_of_urbanization: ['monthly'],
  radar_backscatter_vv: ['weekly', 'monthly'],
  radar_backscatter_vh: ['weekly', 'monthly'],
  elevation_dem30: ['monthly'],
  elevation_srtm: ['monthly'],
  dw_trees: ['weekly', 'monthly'],
  dw_grass: ['weekly', 'monthly'],
  dw_flooded_vegetation: ['weekly', 'monthly'],
  dw_shrub_scrub: ['weekly', 'monthly'],
  dw_bare: ['weekly', 'monthly'],
  dw_snow_ice: ['weekly', 'monthly'],
  wind_speed_10m: ['daily', 'monthly'],
  relative_humidity_2m: ['daily', 'monthly'],
  surface_pressure: ['daily', 'monthly'],
  solar_radiation_down: ['daily', 'monthly'],
  snow_depth_era5: ['daily', 'monthly'],
  runoff_era5: ['daily', 'monthly'],
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

  if (granularity === "daily") {
    const diffDays = Math.floor((endDate.getTime() - startDate.getTime()) / msPerDay);
    return diffDays + 1;
  }

  if (granularity === "weekly") {
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
