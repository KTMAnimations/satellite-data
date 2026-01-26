import { useState, useMemo, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { MapView } from '../components/Map/MapContainer';
import { HeatmapLegend } from '../components/Map/HeatmapLegend';
import { TimeSeriesChart } from '../components/Charts/TimeSeriesChart';
import { SeasonalBarChart } from '../components/Charts/SeasonalBarChart';
import { YearOverYearChart } from '../components/Charts/YearOverYearChart';
import { CorrelationScatter } from '../components/Charts/CorrelationScatter';
import { TimeSlider } from '../components/Charts/TimeSlider';
import { useStore } from '../store';
import api from '../services/api';
import type { MetricType } from '../types';
import './AnalysisView.css';

// Parse date string to local Date (avoiding UTC timezone issues)
// Handles both "YYYY-MM" (monthly) and "YYYY-MM-DD" (weekly/daily) formats
function parseDate(dateStr: string): Date {
  const parts = dateStr.split('-').map(Number);
  const year = parts[0];
  const month = parts[1] - 1; // Month is 0-indexed in JavaScript
  const day = parts[2] || 1;
  return new Date(year, month, day);
}

const METRIC_OPTIONS: { value: MetricType; label: string; color: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights', color: '#D97706' },  // Amber-600
  { value: 'ndvi', label: 'NDVI (Vegetation)', color: '#059669' },        // Emerald-600
  { value: 'urban_density', label: 'Urban Density', color: '#7C3AED' },   // Violet-600
  { value: 'parking', label: 'Parking Occupancy', color: '#0D9488' },     // Teal-600
  { value: 'land_cover', label: 'Land Cover', color: '#9333EA' },         // Purple-600
  { value: 'surface_water', label: 'Surface Water', color: '#2563EB' },   // Blue-600
  { value: 'active_fire', label: 'Active Fire', color: '#DC2626' },       // Red-600
  { value: 'no2', label: 'NO₂ Pollution', color: '#6366F1' },             // Indigo-600
  { value: 'temperature', label: 'Temperature', color: '#EF4444' },       // Red-500
  { value: 'precipitation', label: 'Precipitation', color: '#3B82F6' },   // Blue-500
  { value: 'aerosol', label: 'Aerosol Index', color: '#92400E' },         // Brown-600
  { value: 'cropland', label: 'Cropland', color: '#16A34A' },             // Green-600
  { value: 'evapotranspiration', label: 'Evapotranspiration', color: '#0D9488' }, // Teal-600
  { value: 'soil_moisture', label: 'Soil Moisture', color: '#7C3AED' },   // Violet-600
  { value: 'impervious', label: 'Impervious Surface', color: '#6B7280' }, // Gray-500
  { value: 'fire_historical', label: 'Historical Fire', color: '#EA580C' }, // Orange-600
  { value: 'canopy_height', label: 'Canopy Height', color: '#15803D' },   // Green-700
];

// Finest available granularity per metric (based on data source limitations)
const METRIC_GRANULARITY: Record<MetricType, 'daily' | 'weekly' | 'monthly'> = {
  ndvi: 'weekly',           // Sentinel-2: 5-day revisit
  parking: 'weekly',        // Sentinel-2: 5-day revisit
  nightlights: 'monthly',   // VIIRS: monthly composites only
  urban_density: 'monthly', // GHSL: static epochs
  land_cover: 'weekly',     // Dynamic World: near real-time
  surface_water: 'monthly', // JRC GSW: monthly history
  active_fire: 'daily',     // VIIRS 375m: daily
  no2: 'daily',             // Sentinel-5P: daily
  temperature: 'daily',     // ERA5-Land: hourly aggregated to daily
  precipitation: 'daily',   // ERA5-Land: hourly aggregated to daily
  aerosol: 'daily',         // Sentinel-5P: daily
  cropland: 'monthly',      // USDA CDL: annual
  evapotranspiration: 'monthly', // OpenET: monthly
  soil_moisture: 'weekly',  // SMAP: 3-day
  impervious: 'monthly',    // GAIA: annual
  fire_historical: 'monthly', // FIRMS: daily aggregated
  canopy_height: 'monthly', // GEDI: static
};

type ViewMode = 'charts' | 'correlation' | 'yoy';

export function AnalysisView() {
  const { regionId } = useParams<{ regionId: string }>();
  const { selectedMetrics, toggleMetric, dateRange, setDateRange } = useStore();

  const [selectedMapMetric, setSelectedMapMetric] = useState<MetricType>('nightlights');
  const [viewMode, setViewMode] = useState<ViewMode>('charts');
  const [correlationMetricX, setCorrelationMetricX] = useState<MetricType>('nightlights');
  const [correlationMetricY, setCorrelationMetricY] = useState<MetricType>('ndvi');
  const [isTimelinePlaying, setIsTimelinePlaying] = useState(false);
  const [currentTimelineDate, setCurrentTimelineDate] = useState<Date | null>(null);

  const { data: region } = useQuery({
    queryKey: ['region', regionId],
    queryFn: () => api.getRegion(regionId!),
    enabled: !!regionId,
  });

  // Use finest granularity based on selected map metric
  const granularity = METRIC_GRANULARITY[selectedMapMetric];
  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['metrics', regionId, selectedMapMetric, granularity, dateRange],
    queryFn: () =>
      api.getMetrics(regionId!, {
        start_date: dateRange.start.toISOString().split('T')[0],
        end_date: dateRange.end.toISOString().split('T')[0],
        granularity,
      }),
    enabled: !!regionId,
  });

  // Generate timeline dates from metrics
  const timelineDates = useMemo(() => {
    if (!metrics?.metrics[selectedMapMetric]?.data) return [];
    return metrics.metrics[selectedMapMetric].data.map((d) => parseDate(d.date));
  }, [metrics, selectedMapMetric]);

  // Generate Year-over-Year data
  const yoyData = useMemo((): Record<MetricType, { year: number; value: number }[]> => {
    if (!metrics) return {
      nightlights: [],
      ndvi: [],
      urban_density: [],
      parking: [],
      land_cover: [],
      surface_water: [],
      active_fire: [],
      no2: [],
      temperature: [],
      precipitation: [],
      aerosol: [],
      cropland: [],
      evapotranspiration: [],
      soil_moisture: [],
      impervious: [],
      fire_historical: [],
      canopy_height: [],
    };

    const result: Record<MetricType, { year: number; value: number }[]> = {
      nightlights: [],
      ndvi: [],
      urban_density: [],
      parking: [],
      land_cover: [],
      surface_water: [],
      active_fire: [],
      no2: [],
      temperature: [],
      precipitation: [],
      aerosol: [],
      cropland: [],
      evapotranspiration: [],
      soil_moisture: [],
      impervious: [],
      fire_historical: [],
      canopy_height: [],
    };

    Object.entries(metrics.metrics).forEach(([metric, data]) => {
      const byYear: Record<number, number[]> = {};

      data.data.forEach((d) => {
        const year = new Date(d.date).getFullYear();
        if (!byYear[year]) byYear[year] = [];
        byYear[year].push(d.value);
      });

      result[metric as MetricType] = Object.entries(byYear).map(([year, values]) => ({
        year: parseInt(year),
        value: values.reduce((a, b) => a + b, 0) / values.length,
      }));
    });

    return result;
  }, [metrics]);

  // Generate correlation data
  const correlationData = useMemo(() => {
    if (!metrics) return [];

    const metricXData = metrics.metrics[correlationMetricX]?.data || [];
    const metricYData = metrics.metrics[correlationMetricY]?.data || [];

    // Match by date
    const points: { x: number; y: number; date: string }[] = [];

    metricXData.forEach((xPoint) => {
      const yPoint = metricYData.find((y) => y.date === xPoint.date);
      if (yPoint) {
        points.push({
          x: xPoint.value,
          y: yPoint.value,
          date: xPoint.date,
        });
      }
    });

    return points;
  }, [metrics, correlationMetricX, correlationMetricY]);

  // Initialize and reset timeline date when dates change
  useEffect(() => {
    if (timelineDates.length > 0) {
      // Always reset to first date when timeline dates change
      setCurrentTimelineDate(timelineDates[0]);
    }
  }, [timelineDates]);

  if (!regionId) {
    return (
      <div className="analysis-view">
        <div className="no-region">
          <div className="no-region-icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
          </div>
          <h2>No Region Selected</h2>
          <p>Select a region from the explorer to view its analysis.</p>
          <Link to="/regions" className="btn btn-primary">
            Explore Regions
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="analysis-view">
      {/* Header */}
      <header className="analysis-header">
        <div className="header-info">
          <Link to="/regions" className="back-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Regions
          </Link>
          <div className="header-title">
            <h1>{region?.name || 'Loading...'}</h1>
            {region && (
              <div className="region-meta">
                {region.state_province && <span>{region.state_province}</span>}
                {region.country && <span>{region.country}</span>}
                {region.category && (
                  <span className={`badge badge-${region.category === 'migration_hotspot' ? 'orange' : 'cyan'}`}>
                    {region.category.replace('_', ' ')}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="header-actions">
          <Link to={`/compare/${regionId}`} className="btn btn-outline">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="18" rx="1" />
              <rect x="14" y="3" width="7" height="18" rx="1" />
            </svg>
            Compare
          </Link>
          <Link to={`/exports?region=${regionId}`} className="btn btn-primary">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" />
            </svg>
            Export
          </Link>
        </div>
      </header>

      <div className="analysis-content">
        {/* Left Panel - Map & Controls */}
        <aside className="analysis-sidebar">
          {/* Map */}
          <div className="map-section">
            <div className="section-header">
              <h4>Map View</h4>
              <select
                value={selectedMapMetric}
                onChange={(e) => setSelectedMapMetric(e.target.value as MetricType)}
                className="metric-select"
              >
                {METRIC_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="map-container-wrapper">
              {region && (
                <MapView
                  regions={[region]}
                  selectedMetric={selectedMapMetric}
                  tileDate={currentTimelineDate?.toISOString().split('T')[0] || dateRange.start.toISOString().split('T')[0]}
                />
              )}
              <div className="map-legend-overlay">
                <HeatmapLegend metric={selectedMapMetric} showValues={false} />
              </div>
            </div>

            {/* Timeline Slider */}
            {timelineDates.length > 0 && currentTimelineDate && (
              <div className="timeline-section">
                <TimeSlider
                  dates={timelineDates}
                  selectedDate={currentTimelineDate}
                  onDateChange={setCurrentTimelineDate}
                  isPlaying={isTimelinePlaying}
                  onPlayPause={() => setIsTimelinePlaying(!isTimelinePlaying)}
                  width={280}
                />
              </div>
            )}
          </div>

          {/* Metric Toggles */}
          <div className="metrics-section">
            <h4>Metrics</h4>
            <div className="metric-toggles">
              {METRIC_OPTIONS.map((opt) => (
                <label key={opt.value} className="metric-toggle">
                  <input
                    type="checkbox"
                    checked={selectedMetrics.includes(opt.value)}
                    onChange={() => toggleMetric(opt.value)}
                  />
                  <span
                    className="toggle-indicator"
                    style={{ backgroundColor: selectedMetrics.includes(opt.value) ? opt.color : 'var(--surface-recessed)' }}
                  />
                  <span className="toggle-label">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Date Range */}
          <div className="date-section">
            <h4>Date Range</h4>
            <div className="date-inputs">
              <input
                type="date"
                value={dateRange.start.toISOString().split('T')[0]}
                onChange={(e) =>
                  setDateRange({ ...dateRange, start: new Date(e.target.value) })
                }
              />
              <span className="date-separator">to</span>
              <input
                type="date"
                value={dateRange.end.toISOString().split('T')[0]}
                onChange={(e) =>
                  setDateRange({ ...dateRange, end: new Date(e.target.value) })
                }
              />
            </div>
            <div className="date-presets">
              <button
                className="preset-btn"
                onClick={() =>
                  setDateRange({
                    start: new Date(2024, 0, 1),
                    end: new Date(2024, 0, 31),
                  })
                }
              >
                Jan 2024
              </button>
              <button
                className="preset-btn"
                onClick={() =>
                  setDateRange({
                    start: new Date(new Date().getFullYear() - 1, 0, 1),
                    end: new Date(),
                  })
                }
              >
                Last Year
              </button>
              <button
                className="preset-btn"
                onClick={() =>
                  setDateRange({
                    start: new Date(2020, 0, 1),
                    end: new Date(2022, 11, 31),
                  })
                }
              >
                COVID Era
              </button>
              <button
                className="preset-btn"
                onClick={() =>
                  setDateRange({
                    start: new Date(2015, 0, 1),
                    end: new Date(),
                  })
                }
              >
                Full Archive
              </button>
            </div>
          </div>
        </aside>

        {/* Main Content - Charts */}
        <main className="analysis-main">
          {/* View Mode Tabs */}
          <div className="view-tabs">
            <button
              className={`view-tab ${viewMode === 'charts' ? 'active' : ''}`}
              onClick={() => setViewMode('charts')}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M3 3v18h18" />
                <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3" />
              </svg>
              Time Series
            </button>
            <button
              className={`view-tab ${viewMode === 'yoy' ? 'active' : ''}`}
              onClick={() => setViewMode('yoy')}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M3 9h18M9 21V9" />
              </svg>
              Year over Year
            </button>
            <button
              className={`view-tab ${viewMode === 'correlation' ? 'active' : ''}`}
              onClick={() => setViewMode('correlation')}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="7.5" cy="7.5" r="2.5" />
                <circle cx="16.5" cy="16.5" r="2.5" />
                <path d="M7.5 16.5L16.5 7.5" />
              </svg>
              Correlation
            </button>
          </div>

          {metricsLoading ? (
            <div className="loading-state">
              <div className="loading-spinner" />
              <span>Loading metrics...</span>
            </div>
          ) : metrics ? (
            <>
              {viewMode === 'charts' && (
                <div className="charts-grid stagger-children">
                  {/* Time Series Chart */}
                  <div className="chart-card">
                    <div className="chart-card-header">
                      <h3>Activity Over Time</h3>
                      <span className="chart-subtitle">Monthly averages for selected metrics</span>
                    </div>
                    <TimeSeriesChart
                      data={metrics.metrics}
                      selectedMetrics={selectedMetrics}
                      width={700}
                      height={320}
                    />
                  </div>

                  {/* Seasonal Comparison */}
                  {metrics.seasonal_summary && (
                    <div className="chart-card">
                      <div className="chart-card-header">
                        <h3>Seasonal Comparison</h3>
                        <span className="chart-subtitle">Winter (Dec-Feb) vs Summer (Jun-Aug)</span>
                      </div>
                      <SeasonalBarChart data={metrics.seasonal_summary} width={600} height={280} />
                    </div>
                  )}

                  {/* Stats Grid */}
                  <div className="stats-section">
                    <h4>Summary Statistics</h4>
                    <div className="stats-grid">
                      {selectedMetrics.map((metric) => {
                        const metricData = metrics.metrics[metric];
                        if (!metricData || metricData.data.length === 0) return null;

                        const values = metricData.data.map((d) => d.value);
                        const avg = values.reduce((a, b) => a + b, 0) / values.length;
                        const min = Math.min(...values);
                        const max = Math.max(...values);

                        const seasonalChange = metrics.seasonal_summary?.change_pct[metric];

                        return (
                          <div key={metric} className="stat-card">
                            <div
                              className="stat-accent"
                              style={{
                                backgroundColor: METRIC_OPTIONS.find((o) => o.value === metric)?.color,
                              }}
                            />
                            <h5>{METRIC_OPTIONS.find((o) => o.value === metric)?.label}</h5>
                            <div className="stat-value mono">{avg.toFixed(3)}</div>
                            <div className="stat-label">Average ({metricData.unit})</div>
                            <div className="stat-range">
                              <span>Min: {min.toFixed(3)}</span>
                              <span>Max: {max.toFixed(3)}</span>
                            </div>
                            {seasonalChange !== null && seasonalChange !== undefined && (
                              <div
                                className={`seasonal-change ${seasonalChange > 0 ? 'positive' : seasonalChange < 0 ? 'negative' : ''}`}
                              >
                                <span className="change-value">
                                  {seasonalChange > 0 ? '+' : ''}
                                  {seasonalChange.toFixed(1)}%
                                </span>
                                <span className="change-label">seasonal change</span>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {viewMode === 'yoy' && (
                <div className="yoy-view stagger-children">
                  <div className="yoy-controls">
                    <label>Select Metric:</label>
                    <select
                      value={selectedMapMetric}
                      onChange={(e) => setSelectedMapMetric(e.target.value as MetricType)}
                    >
                      {METRIC_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="chart-card">
                    <YearOverYearChart
                      data={yoyData}
                      selectedMetric={selectedMapMetric}
                      width={700}
                      height={400}
                    />
                  </div>
                </div>
              )}

              {viewMode === 'correlation' && (
                <div className="correlation-view stagger-children">
                  <div className="correlation-controls">
                    <div className="control-group">
                      <label>X Axis:</label>
                      <select
                        value={correlationMetricX}
                        onChange={(e) => setCorrelationMetricX(e.target.value as MetricType)}
                      >
                        {METRIC_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="control-group">
                      <label>Y Axis:</label>
                      <select
                        value={correlationMetricY}
                        onChange={(e) => setCorrelationMetricY(e.target.value as MetricType)}
                      >
                        {METRIC_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="chart-card">
                    <CorrelationScatter
                      data={correlationData}
                      xMetric={correlationMetricX}
                      yMetric={correlationMetricY}
                      width={600}
                      height={500}
                      showTrendline
                    />
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="no-data">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M3 3v18h18" />
                <path d="M7 16l4-4 4 4 5-6" opacity="0.3" />
              </svg>
              <p>No data available for this region and time period.</p>
              <p className="hint">Try adjusting the date range or collecting new data.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
