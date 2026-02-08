import type { Granularity, MetricType } from '../../types';
import { useTileTemplate } from '../../hooks/useTileTemplate';
import { METRIC_LABELS, METRIC_UNITS } from '../../config/metrics';
import { COLORMAPS } from './metricStyles';
import './HeatmapLegend.css';

interface HeatmapLegendProps {
  metric: MetricType;
  min?: number;
  max?: number;
  showValues?: boolean;
  tileDate?: string;
  tileGranularity?: Granularity;
}

function toDateBucket(dateStr: string, granularity: Granularity): string {
  return granularity === 'monthly' ? dateStr.slice(0, 7) : dateStr.slice(0, 10);
}

function getLegendScaleLabels(metric: MetricType): { low: string; high: string } {
  if (metric === 'temperature') return { low: 'Cold', high: 'Hot' };
  if (metric === 'precipitation' || metric === 'surface_water' || metric === 'snow_cover' || metric === 'snow_albedo') {
    return { low: 'Dry', high: 'Wet' };
  }
  if (metric === 'nightlights') return { low: 'Dim', high: 'Bright' };
  return { low: 'Low', high: 'High' };
}

export function HeatmapLegend({
  metric,
  min,
  max,
  showValues = true,
  tileDate,
  tileGranularity,
}: HeatmapLegendProps) {
  const label = METRIC_LABELS[metric];
  const unit = METRIC_UNITS[metric];
  const scaleLabels = getLegendScaleLabels(metric);
  const dateBucket = tileDate && tileGranularity ? toDateBucket(tileDate, tileGranularity) : undefined;

  const { data: tileTemplate } = useTileTemplate(metric, dateBucket, tileGranularity);

  const fallbackGradient = `linear-gradient(90deg, ${COLORMAPS[metric].join(', ')})`;
  const gradient =
    tileTemplate?.palette?.length ? `linear-gradient(90deg, ${tileTemplate.palette.join(', ')})` : fallbackGradient;

  return (
    <div className="heatmap-legend">
      <div className="legend-header">
        <span className="legend-title">{label}</span>
        {showValues && min !== undefined && max !== undefined && (
          <span className="legend-range mono">
            {min.toFixed(2)} – {max.toFixed(2)} {unit}
          </span>
        )}
      </div>

      <div className="legend-bar-container">
        <div
          className="legend-gradient-bar"
          style={{ background: gradient }}
        />
        <div className="legend-ticks">
          <span>{scaleLabels.low}</span>
          <span>{scaleLabels.high}</span>
        </div>
      </div>
    </div>
  );
}

// Compact version for map overlays
export function HeatmapLegendCompact({
  metric,
  tileDate,
  tileGranularity,
}: {
  metric: MetricType;
  tileDate?: string;
  tileGranularity?: Granularity;
}) {
  const label = METRIC_LABELS[metric];
  const scaleLabels = getLegendScaleLabels(metric);
  const dateBucket = tileDate && tileGranularity ? toDateBucket(tileDate, tileGranularity) : undefined;

  const { data: tileTemplate } = useTileTemplate(metric, dateBucket, tileGranularity);

  const fallbackGradient = `linear-gradient(90deg, ${COLORMAPS[metric].join(', ')})`;
  const gradient =
    tileTemplate?.palette?.length ? `linear-gradient(90deg, ${tileTemplate.palette.join(', ')})` : fallbackGradient;

  return (
    <div className="heatmap-legend-compact">
      <span className="legend-label">{label}</span>
      <div
        className="legend-bar-mini"
        style={{ background: gradient }}
      />
      <div className="legend-labels-mini">
        <span>{scaleLabels.low}</span>
        <span>{scaleLabels.high}</span>
      </div>
    </div>
  );
}
