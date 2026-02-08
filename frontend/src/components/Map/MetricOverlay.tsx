import { useMemo } from 'react';
import { GeoJSON } from 'react-leaflet';
import type { GeoJSONPolygon, MetricType } from '../../types';
import { VALUE_RANGES, getMetricColormap, interpolateColor } from './metricStyles';

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
    const colors = getMetricColormap(metric);
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
