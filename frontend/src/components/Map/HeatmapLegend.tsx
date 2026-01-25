import type { MetricType } from '../../types';
import './HeatmapLegend.css';

interface HeatmapLegendProps {
  metric: MetricType;
  min?: number;
  max?: number;
  showValues?: boolean;
}

const METRIC_CONFIG: Record<
  MetricType,
  {
    label: string;
    unit: string;
    gradient: string;
    lowLabel: string;
    highLabel: string;
  }
> = {
  nightlights: {
    label: 'Nighttime Lights',
    unit: 'nW/cm²/sr',
    gradient: 'linear-gradient(90deg, #FEF3C7 0%, #FBBF24 30%, #D97706 60%, #B45309 100%)',
    lowLabel: 'Dark',
    highLabel: 'Bright',
  },
  ndvi: {
    label: 'NDVI',
    unit: 'index',
    gradient: 'linear-gradient(90deg, #FEF3C7 0%, #BBF7D0 30%, #22C55E 60%, #059669 100%)',
    lowLabel: 'Barren',
    highLabel: 'Lush',
  },
  urban_density: {
    label: 'Urban Density',
    unit: 'ratio',
    gradient: 'linear-gradient(90deg, #F5F5F4 0%, #C4B5FD 40%, #7C3AED 70%, #5B21B6 100%)',
    lowLabel: 'Rural',
    highLabel: 'Urban',
  },
  parking: {
    label: 'Parking Occupancy',
    unit: 'ratio',
    gradient: 'linear-gradient(90deg, #CCFBF1 0%, #5EEAD4 30%, #0D9488 60%, #0F766E 100%)',
    lowLabel: 'Empty',
    highLabel: 'Full',
  },
};

export function HeatmapLegend({
  metric,
  min,
  max,
  showValues = true,
}: HeatmapLegendProps) {
  const config = METRIC_CONFIG[metric];

  return (
    <div className="heatmap-legend">
      <div className="legend-header">
        <span className="legend-title">{config.label}</span>
        {showValues && min !== undefined && max !== undefined && (
          <span className="legend-range mono">
            {min.toFixed(2)} – {max.toFixed(2)} {config.unit}
          </span>
        )}
      </div>

      <div className="legend-bar-container">
        <div
          className="legend-gradient-bar"
          style={{ background: config.gradient }}
        />
        <div className="legend-ticks">
          <span>{config.lowLabel}</span>
          <span>{config.highLabel}</span>
        </div>
      </div>
    </div>
  );
}

// Compact version for map overlays
export function HeatmapLegendCompact({ metric }: { metric: MetricType }) {
  const config = METRIC_CONFIG[metric];

  return (
    <div className="heatmap-legend-compact">
      <span className="legend-label">{config.label}</span>
      <div
        className="legend-bar-mini"
        style={{ background: config.gradient }}
      />
      <div className="legend-labels-mini">
        <span>{config.lowLabel}</span>
        <span>{config.highLabel}</span>
      </div>
    </div>
  );
}
