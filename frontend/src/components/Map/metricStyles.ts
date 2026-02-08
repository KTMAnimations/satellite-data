import type { MetricType } from '../../types';
import { METRIC_VALUE_RANGES } from '../../config/metricRanges';

// Colormaps matching backend - converted to RGB hex
export const COLORMAPS: Record<MetricType, string[]> = {
  ndvi: [
    '#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b',
    '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837',
  ],
  nightlights: [
    '#e8c36a', '#efd084', '#f3db9d', '#f7e5b6', '#faedcb',
    '#fdf3dc', '#fef8ea', '#fffbf2', '#fffdf8', '#ffffff',
  ],
  surface_water: [
    '#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9',
    '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360',
  ],
  no2: [
    '#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
    '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026',
  ],
  temperature: [
    '#053061', '#2166ac', '#4393c3', '#92c5de', '#d1e5f0',
    '#fddbc7', '#f4a582', '#d6604d', '#b2182b', '#67001f',
  ],
  precipitation: [
    '#ffffff', '#f0f9e8', '#ccebc5', '#a8ddb5', '#7bccc4',
    '#4eb3d3', '#2b8cbe', '#0868ac', '#084081', '#252556',
  ],
  aerosol: [
    '#ffffff', '#fdf5e6', '#fce0c5', '#f9c496', '#f4a267',
    '#dd8541', '#b2672d', '#8a4a1c', '#64320e', '#321405',
  ],
  cropland: [
    '#ffffb2', '#fed976', '#feb24c', '#fd8d3c', '#f03b20',
    '#bd0026', '#228b22', '#32cd32', '#90ee90', '#ffff00',
  ],
  evapotranspiration: [
    '#a6611a', '#bf812d', '#dfc27d', '#e6d8b2', '#f5f5dc',
    '#c7eae5', '#80cdc1', '#35978f', '#01665e', '#003c30',
  ],
  soil_moisture: [
    '#8b4513', '#a0522d', '#bc8f5f', '#d2b48c', '#f5deb3',
    '#add8e6', '#87ceeb', '#4682b4', '#4169e1', '#00008b',
  ],
  impervious: [
    '#ffffff', '#f0f0f0', '#d9d9d9', '#bdbdbd', '#969696',
    '#737373', '#525252', '#363636', '#1a1a1a', '#000000',
  ],
  canopy_height: [
    '#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476',
    '#41ab5d', '#238b45', '#006d2c', '#004d1c', '#00280f',
  ],
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
