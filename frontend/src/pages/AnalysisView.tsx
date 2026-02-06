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
import type { Granularity, MetricType } from '../types';
import {
  estimateBucketCount,
  getRecommendedGranularity,
  METRICS_MAX_TIMESERIES_POINTS_DEFAULT,
  METRIC_SUPPORTED_GRANULARITIES,
} from '../config/metrics';
import { formatDateYYYYMMDD, parseMetricDate } from '../utils/dates';
import { formatApiError } from '../utils/errors';
import { computeMetricDeltaPercentOfRange } from '../utils/metrics';
import './AnalysisView.css';

const METRIC_OPTIONS: { value: MetricType; label: string; color: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights', color: '#D97706' },  // Amber-600
  { value: 'ndvi', label: 'NDVI (Vegetation)', color: '#059669' },        // Emerald-600
  { value: 'urban_density', label: 'Urban Density', color: '#7C3AED' },   // Violet-600
  { value: 'parking', label: 'Parking Occupancy', color: '#0D9488' },     // Teal-600
  { value: 'land_cover', label: 'Land Cover', color: '#9333EA' },         // Purple-600
  { value: 'surface_water', label: 'Surface Water', color: '#2563EB' },   // Blue-600
  { value: 'no2', label: 'NO₂ Pollution', color: '#6366F1' },             // Indigo-600
  { value: 'temperature', label: 'Temperature', color: '#EF4444' },       // Red-500
  { value: 'precipitation', label: 'Precipitation', color: '#3B82F6' },   // Blue-500
  { value: 'aerosol', label: 'Aerosol Index', color: '#92400E' },         // Brown-600
  { value: 'cropland', label: 'Cropland', color: '#16A34A' },             // Green-600
  { value: 'evapotranspiration', label: 'Evapotranspiration', color: '#0D9488' }, // Teal-600
  { value: 'soil_moisture', label: 'Soil Moisture', color: '#7C3AED' },   // Violet-600
  { value: 'impervious', label: 'Impervious Surface', color: '#6B7280' }, // Gray-500
  { value: 'canopy_height', label: 'Canopy Height', color: '#15803D' },   // Green-700
];

type ViewMode = 'charts' | 'correlation' | 'yoy';

function getTimeSeriesNotes(
  metrics: MetricType[],
  dateRange: { start: Date; end: Date }
): Array<{ metric: MetricType; note: string }> {
  const notes: Array<{ metric: MetricType; note: string }> = [];
  const has = (m: MetricType) => metrics.includes(m);
/*
  if (has('surface_water')) {
    notes.push({
      metric: 'surface_water',
      note: 'JRC monthly history ends 2021; newer dates use Dynamic World water probability.',
    });
  }

  if (has('cropland')) {
    notes.push({
      metric: 'cropland',
      note: 'WorldCover cropland mask (2021) × Dynamic World crops probability (seasonal).',
    });
  }

  if (has('impervious') && dateRange.end.getFullYear() > 2018) {
    notes.push({
      metric: 'impervious',
      note: 'GAIA ends in 2018; dates after 2018 show the 2018 extent (flat line is expected).',
    });
  }

  if (has('canopy_height')) {
    notes.push({
      metric: 'canopy_height',
      note: 'Canopy height changes slowly; GEDI coverage is limited and later dates may fall back to a static layer.',
    });
  }
*/
  return notes;
}

export function AnalysisView() {
  const { regionId } = useParams<{ regionId: string }>();
  const { selectedMetrics, toggleMetric, dateRange, setDateRange } = useStore();

  const [selectedMapMetric, setSelectedMapMetric] = useState<MetricType>('nightlights');
  const [selectedGranularity, setSelectedGranularity] = useState<Granularity | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('charts');
  const [correlationMetricX, setCorrelationMetricX] = useState<MetricType>('nightlights');
  const [correlationMetricY, setCorrelationMetricY] = useState<MetricType>('ndvi');
  const [isTimelinePlaying, setIsTimelinePlaying] = useState(false);
  const [currentTimelineDate, setCurrentTimelineDate] = useState<Date | null>(null);
  const [overlayIsLoading, setOverlayIsLoading] = useState(false);

  const handleMapMetricChange = (metric: MetricType) => {
    setSelectedMapMetric(metric);
    // When a user changes the map metric, ensure it also appears in the charts/stats.
    // This keeps the "analysis" view in sync with what is shown on the map.
    if (!selectedMetrics.includes(metric)) toggleMetric(metric);
  };

  const { data: region } = useQuery({
    queryKey: ['region', regionId],
    queryFn: ({ signal }) => api.getRegion(regionId!, { signal }),
    enabled: !!regionId,
  });

  const supportedGranularities = METRIC_SUPPORTED_GRANULARITIES[selectedMapMetric];
  const recommendedGranularity = getRecommendedGranularity(selectedMapMetric, dateRange);
  const selectedGranularityAllowed = Boolean(
    selectedGranularity
      && supportedGranularities.includes(selectedGranularity)
      && estimateBucketCount(dateRange.start, dateRange.end, selectedGranularity) <= METRICS_MAX_TIMESERIES_POINTS_DEFAULT
  );
  const granularity = selectedGranularityAllowed
    ? (selectedGranularity as Granularity)
    : recommendedGranularity;
  const requestedMetrics = useMemo(() => {
    const metricsSet = new Set<MetricType>();
    metricsSet.add(selectedMapMetric);
    for (const metric of selectedMetrics) metricsSet.add(metric);
    if (viewMode === 'correlation') {
      metricsSet.add(correlationMetricX);
      metricsSet.add(correlationMetricY);
    }
    return Array.from(metricsSet).sort();
  }, [correlationMetricX, correlationMetricY, selectedMapMetric, selectedMetrics, viewMode]);

  const { data: metrics, isLoading: metricsLoading, isError: metricsIsError, error: metricsError } = useQuery({
    queryKey: ['metrics', regionId, granularity, dateRange, requestedMetrics],
    queryFn: ({ signal }) =>
      api.getMetrics(regionId!, {
        start_date: formatDateYYYYMMDD(dateRange.start) ?? dateRange.start.toISOString().split('T')[0],
        end_date: formatDateYYYYMMDD(dateRange.end) ?? dateRange.end.toISOString().split('T')[0],
        metrics: requestedMetrics,
        granularity,
      }, { signal }),
    enabled: !!regionId,
  });

  // Generate timeline dates from metrics
  const timelineDates = useMemo(() => {
    if (!metrics?.metrics[selectedMapMetric]?.data) return [];
    return metrics.metrics[selectedMapMetric].data
      .map((d) => parseMetricDate(d.date))
      .flatMap((d) => (d && !Number.isNaN(d.getTime()) ? [d] : []))
      .sort((a, b) => a.getTime() - b.getTime())
      .filter((d, i, arr) => i === 0 || d.getTime() !== arr[i - 1].getTime());
  }, [metrics, selectedMapMetric]);

  // Generate Year-over-Year data
  const yoyData = useMemo((): Record<MetricType, { year: number; value: number }[]> => {
    if (!metrics || viewMode !== 'yoy') return {
      nightlights: [],
      ndvi: [],
      urban_density: [],
      parking: [],
      land_cover: [],
      surface_water: [],
      no2: [],
      temperature: [],
      precipitation: [],
      aerosol: [],
      cropland: [],
      evapotranspiration: [],
      soil_moisture: [],
      impervious: [],
      canopy_height: [],
    };

    const result: Record<MetricType, { year: number; value: number }[]> = {
      nightlights: [],
      ndvi: [],
      urban_density: [],
      parking: [],
      land_cover: [],
      surface_water: [],
      no2: [],
      temperature: [],
      precipitation: [],
      aerosol: [],
      cropland: [],
      evapotranspiration: [],
      soil_moisture: [],
      impervious: [],
      canopy_height: [],
    };

    Object.entries(metrics.metrics).forEach(([metric, data]) => {
      const byYear: Record<number, number[]> = {};

      data.data.forEach((d) => {
        const parsed = parseMetricDate(d.date);
        if (!parsed) return;
        const year = parsed.getFullYear();
        if (!byYear[year]) byYear[year] = [];
        byYear[year].push(d.value);
      });

      result[metric as MetricType] = Object.entries(byYear).map(([year, values]) => ({
        year: parseInt(year),
        value: values.reduce((a, b) => a + b, 0) / values.length,
      }));
    });

    return result;
  }, [metrics, viewMode]);

  // Generate correlation data
  const correlationData = useMemo(() => {
    if (!metrics || viewMode !== 'correlation') return [];

    const metricXData = metrics.metrics[correlationMetricX]?.data || [];
    const metricYData = metrics.metrics[correlationMetricY]?.data || [];

    // Match by date in O(n) instead of O(n²)
    const yByDate = new Map(metricYData.map((p) => [p.date, p.value]));
    return metricXData.flatMap((xPoint) => {
      const yValue = yByDate.get(xPoint.date);
      if (yValue === undefined) return [];
      return [{ x: xPoint.value, y: yValue, date: xPoint.date }];
    });
  }, [metrics, correlationMetricX, correlationMetricY, viewMode]);

  const timeSeriesNotes = useMemo(
    () => getTimeSeriesNotes(selectedMetrics, dateRange),
    [selectedMetrics, dateRange]
  );

  // Reset timeline date and granularity when metric changes
  useEffect(() => {
    setCurrentTimelineDate(null);
    setSelectedGranularity(null);
  }, [selectedMapMetric]);

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

  const tileDate =
    formatDateYYYYMMDD(currentTimelineDate)
    ?? formatDateYYYYMMDD(dateRange.start)
    ?? formatDateYYYYMMDD(new Date())
    ?? new Date().toISOString().split('T')[0];

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
          <Link to={`/map/${regionId}`} className="btn btn-outline">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z" />
              <path d="M9 3v15" />
              <path d="M15 6v15" />
            </svg>
            Full Map
          </Link>
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
                onChange={(e) => handleMapMetricChange(e.target.value as MetricType)}
                className="metric-select"
              >
                {METRIC_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {supportedGranularities.length > 1 && (
                <div className="granularity-toggle">
                  {supportedGranularities.map((g) => {
                    const withinLimit =
                      estimateBucketCount(dateRange.start, dateRange.end, g) <= METRICS_MAX_TIMESERIES_POINTS_DEFAULT;
                    const label = g.charAt(0).toUpperCase() + g.slice(1);

                    return (
                      <button
                        key={g}
                        className={`granularity-btn ${granularity === g ? 'active' : ''}`}
                        onClick={() => setSelectedGranularity(g)}
                        disabled={!withinLimit}
                        title={withinLimit ? undefined : `Date range too large for ${label.toLowerCase()} granularity`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="map-container-wrapper">
                  {region && (
                    <MapView
                      regions={[region]}
                      selectedMetric={selectedMapMetric}
                      tileGranularity={granularity}
                      tileDate={tileDate}
                      onOverlayLoadingChange={setOverlayIsLoading}
                    />
                  )}
                  <div className="map-legend-overlay">
                    <HeatmapLegend
                      metric={selectedMapMetric}
                      showValues={false}
                      tileDate={tileDate}
                      tileGranularity={granularity}
                    />
                  </div>
                </div>

            {/* Timeline Slider */}
            {timelineDates.length > 0 && currentTimelineDate && !isNaN(currentTimelineDate.getTime()) && (
              <div className="timeline-section">
                <TimeSlider
                  dates={timelineDates}
                  selectedDate={currentTimelineDate}
                  onDateChange={setCurrentTimelineDate}
                  isPlaying={isTimelinePlaying}
                  playbackBlocked={overlayIsLoading}
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
                value={formatDateYYYYMMDD(dateRange.start) ?? dateRange.start.toISOString().split('T')[0]}
                onChange={(e) =>
                  setDateRange({ ...dateRange, start: parseMetricDate(e.target.value) ?? new Date(e.target.value) })
                }
              />
              <span className="date-separator">to</span>
              <input
                type="date"
                value={formatDateYYYYMMDD(dateRange.end) ?? dateRange.end.toISOString().split('T')[0]}
                onChange={(e) =>
                  setDateRange({ ...dateRange, end: parseMetricDate(e.target.value) ?? new Date(e.target.value) })
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
          ) : metricsIsError ? (
            <div className="no-data">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 9v4" />
                <path d="M12 17h.01" />
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <p>Failed to load metrics for this region.</p>
              <p className="hint">{formatApiError(metricsError)}</p>
            </div>
          ) : metrics ? (
            <>
              {viewMode === 'charts' && (
                <div className="charts-grid stagger-children">
                  {/* Time Series Chart */}
                  <div className="chart-card">
                    <div className="chart-card-header">
                      <h3>Activity Over Time</h3>
                      <span className="chart-subtitle">Auto granularity by metric (daily/weekly/monthly)</span>
                    </div>
                    <TimeSeriesChart
                      data={metrics.metrics}
                      selectedMetrics={selectedMetrics}
                      width={700}
                      height={320}
                    />
                    {timeSeriesNotes.length > 0 && (
                      <div className="chart-note" role="note">
                        {timeSeriesNotes.map(({ metric, note }) => (
                          <div key={metric} className="chart-note-line">
                            <strong>{METRIC_OPTIONS.find((o) => o.value === metric)?.label ?? metric}:</strong> {note}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Seasonal Comparison */}
                  {metrics.seasonal_summary && (
                    <div className="chart-card">
                      <div className="chart-card-header">
                        <h3>Seasonal Comparison</h3>
                        <span className="chart-subtitle">Winter (Dec-Feb) vs Summer (Jun-Aug)</span>
                      </div>
                      <SeasonalBarChart data={metrics.seasonal_summary} selectedMetrics={selectedMetrics} width={600} height={280} />
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
                        const valueDigits = Math.max(Math.abs(avg), Math.abs(min), Math.abs(max)) < 1 ? 4 : 3;

                        const winterAvg = metrics.seasonal_summary?.winter_avg[metric];
                        const summerAvg = metrics.seasonal_summary?.summer_avg[metric];
                        const seasonalChange =
                          winterAvg === null || winterAvg === undefined || summerAvg === null || summerAvg === undefined
                            ? null
                            : computeMetricDeltaPercentOfRange(metric, winterAvg, summerAvg);

                        return (
                          <div key={metric} className="stat-card">
                            <div
                              className="stat-accent"
                              style={{
                                backgroundColor: METRIC_OPTIONS.find((o) => o.value === metric)?.color,
                              }}
                            />
                            <h5>{METRIC_OPTIONS.find((o) => o.value === metric)?.label}</h5>
                            <div className="stat-value mono">{avg.toFixed(valueDigits)}</div>
                            <div className="stat-label">Average ({metricData.unit})</div>
                            <div className="stat-range">
                              <span>Min: {min.toFixed(valueDigits)}</span>
                              <span>Max: {max.toFixed(valueDigits)}</span>
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
                      {/* Show message if no stats available */}
                      {selectedMetrics.every((metric) => {
                        const metricData = metrics.metrics[metric];
                        return !metricData || metricData.data.length === 0;
                      }) && (
                        <div className="no-stats-message" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '24px', color: '#78716C' }}>
                          <p style={{ margin: 0, fontSize: '14px' }}>No statistics available</p>
                          <p style={{ margin: '8px 0 0', fontSize: '12px', opacity: 0.7 }}>
                            Try adjusting the date range or selecting different metrics
                          </p>
                        </div>
                      )}
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
                      onChange={(e) => handleMapMetricChange(e.target.value as MetricType)}
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
              <p>No metrics available for this region and time period.</p>
              <p className="hint">Try adjusting the date range or selecting different metrics.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
