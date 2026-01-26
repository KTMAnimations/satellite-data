import { useMemo } from 'react';
import { GeoJSON } from 'react-leaflet';
import type { GeoJSONPolygon, MetricType } from '../../types';

// Colormaps matching backend - converted to RGB hex
const COLORMAPS: Record<MetricType, string[]> = {
  ndvi: [
    '#a50026', // -1: Dark red
    '#d73027', // -0.5: Red
    '#f46d43', // 0: Orange
    '#fdae61', // 0.25: Light orange
    '#fee08b', // 0.5: Yellow
    '#d9ef8b', // 0.6: Light green
    '#a6d96a', // 0.7: Green
    '#66bd63', // 0.8: Darker green
    '#1a9850', // 0.9: Dark green
    '#006837', // 1: Very dark green
  ],
  nightlights: [
    '#000000', // 0: Black
    '#1e0032', // Low: Dark purple
    '#3c0064', //
    '#640096', //
    '#963296', //
    '#c86464', //
    '#ff9632', // Medium: Orange
    '#ffc864', //
    '#ffff96', //
    '#ffffff', // High: White
  ],
  urban_density: [
    '#ffffe5', // 0: Light yellow
    '#fff7bc',
    '#fee391',
    '#fec44f',
    '#fe9929',
    '#ec7014',
    '#cc4c02',
    '#993404',
    '#662506',
    '#331203', // 1: Dark brown
  ],
  parking: [
    '#f7fbff', // 0: Very light blue
    '#deebf7',
    '#c6dbef',
    '#9ecae1',
    '#6baed6',
    '#4292c6',
    '#2171b5',
    '#08519c',
    '#08306b',
    '#03132b', // 1: Very dark blue
  ],
};

// Value ranges for each metric
const VALUE_RANGES: Record<MetricType, [number, number]> = {
  ndvi: [-1.0, 1.0],
  nightlights: [0.0, 100.0],
  urban_density: [0.0, 1.0],
  parking: [0.0, 1.0],
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
