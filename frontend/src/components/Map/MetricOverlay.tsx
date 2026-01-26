import { useMemo } from 'react';
import { GeoJSON } from 'react-leaflet';
import type { GeoJSONPolygon, MetricType } from '../../types';

// Colormaps matching backend - converted to RGB hex
const COLORMAPS: Record<MetricType, string[]> = {
  ndvi: [
    '#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b',
    '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837',
  ],
  nightlights: [
    '#000000', '#1e0032', '#3c0064', '#640096', '#963296',
    '#c86464', '#ff9632', '#ffc864', '#ffff96', '#ffffff',
  ],
  urban_density: [
    '#ffffe5', '#fff7bc', '#fee391', '#fec44f', '#fe9929',
    '#ec7014', '#cc4c02', '#993404', '#662506', '#331203',
  ],
  parking: [
    '#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6',
    '#4292c6', '#2171b5', '#08519c', '#08306b', '#03132b',
  ],
  land_cover: [
    '#f7f4f9', '#e7e1ef', '#d4b9da', '#c994c7', '#ba6eb4',
    '#aa4da0', '#98318b', '#7a0177', '#5c015e', '#3f003c',
  ],
  surface_water: [
    '#ffffff', '#f0f9ff', '#d6eaf8', '#aed6f1', '#85c1e9',
    '#5dade2', '#3498db', '#2980b9', '#1f618d', '#154360',
  ],
  active_fire: [
    '#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c',
    '#fc4e2a', '#e31a1c', '#bd0026', '#800026', '#500000',
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
  fire_historical: [
    '#ffffcc', '#ffeda0', '#fed976', '#feb24c', '#fd8d3c',
    '#fc4e2a', '#e31a1c', '#bd0026', '#800026', '#500000',
  ],
  canopy_height: [
    '#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476',
    '#41ab5d', '#238b45', '#006d2c', '#004d1c', '#00280f',
  ],
};

// Value ranges for each metric
const VALUE_RANGES: Record<MetricType, [number, number]> = {
  ndvi: [-1.0, 1.0],
  nightlights: [0.0, 100.0],
  urban_density: [0.0, 1.0],
  parking: [0.0, 1.0],
  land_cover: [0.0, 1.0],
  surface_water: [0.0, 1.0],
  active_fire: [0.0, 500.0],
  no2: [0.0, 0.0002],
  temperature: [-30.0, 45.0],
  precipitation: [0.0, 500.0],
  aerosol: [-2.0, 5.0],
  cropland: [0.0, 255.0],
  evapotranspiration: [0.0, 300.0],
  soil_moisture: [0.0, 50.0],
  impervious: [0.0, 1.0],
  fire_historical: [0.0, 500.0],
  canopy_height: [0.0, 60.0],
};

function interpolateColor(colors: string[], t: number): string {
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

interface MetricOverlayProps {
  geometry: GeoJSONPolygon;
  metric: MetricType;
  value: number | null;
  opacity?: number;
}

export function MetricOverlay({
  geometry,
  metric,
  value,
  opacity = 0.6,
}: MetricOverlayProps) {
  const style = useMemo(() => {
    if (value === null) {
      return {
        fillColor: '#888888',
        fillOpacity: 0.2,
        color: '#666666',
        weight: 1,
        opacity: 0.5,
      };
    }

    const [vmin, vmax] = VALUE_RANGES[metric];
    const normalized = (value - vmin) / (vmax - vmin);
    const colors = COLORMAPS[metric];
    const fillColor = interpolateColor(colors, normalized);

    return {
      fillColor,
      fillOpacity: opacity,
      color: fillColor,
      weight: 2,
      opacity: 0.8,
    };
  }, [metric, value, opacity]);

  // Create a unique key that changes when value changes to force re-render
  const key = `${metric}-${value}-${opacity}`;

  return (
    <GeoJSON
      key={key}
      data={geometry as GeoJSON.Geometry}
      style={() => style}
    />
  );
}

// Export colormaps for use in legends
export { COLORMAPS, VALUE_RANGES, interpolateColor };
