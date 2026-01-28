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
  land_cover: {
    label: 'Land Cover',
    unit: 'probability',
    gradient: 'linear-gradient(90deg, #F7F4F9 0%, #D4B9DA 30%, #C994C7 60%, #980043 100%)',
    lowLabel: 'Natural',
    highLabel: 'Built-up',
  },
  surface_water: {
    label: 'Surface Water',
    unit: 'presence',
    gradient: 'linear-gradient(90deg, #FFFFFF 0%, #D4E6F1 30%, #5DADE2 60%, #154360 100%)',
    lowLabel: 'Land',
    highLabel: 'Water',
  },
  active_fire: {
    label: 'Active Fire',
    unit: 'MW',
    gradient: 'linear-gradient(90deg, #FFFFCC 0%, #FED976 30%, #FD8D3C 60%, #800000 100%)',
    lowLabel: 'None',
    highLabel: 'Intense',
  },
  no2: {
    label: 'NO₂',
    unit: 'mol/m²',
    gradient: 'linear-gradient(90deg, #313695 0%, #74ADD1 25%, #FFFFBF 50%, #F46D43 75%, #A50026 100%)',
    lowLabel: 'Low',
    highLabel: 'High',
  },
  temperature: {
    label: 'Temperature',
    unit: '°C',
    gradient: 'linear-gradient(90deg, #053061 0%, #4393C3 25%, #F7F7F7 50%, #D6604D 75%, #67001F 100%)',
    lowLabel: 'Cold',
    highLabel: 'Hot',
  },
  precipitation: {
    label: 'Precipitation',
    unit: 'mm',
    gradient: 'linear-gradient(90deg, #FFFFFF 0%, #C7E9C0 25%, #74C476 50%, #238B45 75%, #252556 100%)',
    lowLabel: 'Dry',
    highLabel: 'Wet',
  },
  aerosol: {
    label: 'Aerosol',
    unit: 'index',
    gradient: 'linear-gradient(90deg, #FFFFFF 0%, #FDE0C5 30%, #EB9F72 60%, #321405 100%)',
    lowLabel: 'Clear',
    highLabel: 'Smoky',
  },
  cropland: {
    label: 'Cropland',
    unit: 'ratio',
    gradient: 'linear-gradient(90deg, #FFFFB2 0%, #FED976 25%, #FD8D3C 50%, #BD0026 75%, #228B22 100%)',
    lowLabel: 'Fallow',
    highLabel: 'Crops',
  },
  evapotranspiration: {
    label: 'Evapotranspiration',
    unit: 'mm',
    gradient: 'linear-gradient(90deg, #A6611A 0%, #DFC27D 30%, #80CDC1 60%, #003C30 100%)',
    lowLabel: 'Low',
    highLabel: 'High',
  },
  soil_moisture: {
    label: 'Soil Moisture',
    unit: 'm³/m³',
    gradient: 'linear-gradient(90deg, #8B4513 0%, #D2B48C 30%, #ADD8E6 60%, #00008B 100%)',
    lowLabel: 'Dry',
    highLabel: 'Wet',
  },
  impervious: {
    label: 'Impervious Surface',
    unit: 'presence',
    gradient: 'linear-gradient(90deg, #FFFFFF 0%, #D9D9D9 30%, #969696 60%, #000000 100%)',
    lowLabel: 'Natural',
    highLabel: 'Paved',
  },
  fire_historical: {
    label: 'Historical Fire',
    unit: 'MW',
    gradient: 'linear-gradient(90deg, #FFFFCC 0%, #FED976 30%, #FD8D3C 60%, #800000 100%)',
    lowLabel: 'None',
    highLabel: 'Intense',
  },
  canopy_height: {
    label: 'Canopy Height',
    unit: 'm',
    gradient: 'linear-gradient(90deg, #F7FCF5 0%, #C7E9C0 30%, #74C476 60%, #00280F 100%)',
    lowLabel: 'Short',
    highLabel: 'Tall',
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
