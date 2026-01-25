import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { MapView } from '../components/Map/MapContainer';
import { TimeSeriesChart } from '../components/Charts/TimeSeriesChart';
import { SeasonalBarChart } from '../components/Charts/SeasonalBarChart';
import { useStore } from '../store';
import api from '../services/api';
import type { MetricType } from '../types';
import './AnalysisView.css';

const METRIC_OPTIONS: { value: MetricType; label: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights' },
  { value: 'ndvi', label: 'NDVI (Vegetation)' },
  { value: 'urban_density', label: 'Urban Density' },
  { value: 'parking', label: 'Parking Occupancy' },
];

export function AnalysisView() {
  const { regionId } = useParams<{ regionId: string }>();
  const { selectedMetrics, toggleMetric, dateRange, setDateRange } = useStore();

  const [selectedMapMetric, setSelectedMapMetric] = useState<MetricType>('nightlights');
  const [compareMode, setCompareMode] = useState(false);

  const { data: region } = useQuery({
    queryKey: ['region', regionId],
    queryFn: () => api.getRegion(regionId!),
    enabled: !!regionId,
  });

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['metrics', regionId, dateRange],
    queryFn: () =>
      api.getMetrics(regionId!, {
        start_date: dateRange.start.toISOString().split('T')[0],
        end_date: dateRange.end.toISOString().split('T')[0],
        granularity: 'monthly',
      }),
    enabled: !!regionId,
  });

  const { data: analyses } = useQuery({
    queryKey: ['analyses', regionId],
    queryFn: () => api.getRegionAnalyses(regionId!),
    enabled: !!regionId,
  });

  if (!regionId) {
    return (
      <div className="analysis-view">
        <div className="no-region">
          <h2>No Region Selected</h2>
          <p>Select a region from the explorer to view its analysis.</p>
          <Link to="/regions" className="btn btn-primary">
            Go to Region Explorer
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
            ← Back to Regions
          </Link>
          <h1>{region?.name || 'Loading...'}</h1>
          {region && (
            <p>
              {region.state_province && `${region.state_province}, `}
              {region.country}
              {region.category && (
                <span className="category-badge">{region.category.replace('_', ' ')}</span>
              )}
            </p>
          )}
        </div>
        <div className="header-actions">
          <Link to={`/exports?region=${regionId}`} className="btn btn-outline">
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
              <h3>Map View</h3>
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
            <div className="map-container-small">
              {region && (
                <MapView
                  regions={[region]}
                  selectedMetric={selectedMapMetric}
                />
              )}
            </div>
          </div>

          {/* Metric Toggles */}
          <div className="metrics-section">
            <h3>Metrics</h3>
            <div className="metric-toggles">
              {METRIC_OPTIONS.map((opt) => (
                <label key={opt.value} className="metric-toggle">
                  <input
                    type="checkbox"
                    checked={selectedMetrics.includes(opt.value)}
                    onChange={() => toggleMetric(opt.value)}
                  />
                  <span className={`toggle-label metric-${opt.value}`}>{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Date Range */}
          <div className="date-section">
            <h3>Date Range</h3>
            <div className="date-inputs">
              <input
                type="date"
                value={dateRange.start.toISOString().split('T')[0]}
                onChange={(e) =>
                  setDateRange({ ...dateRange, start: new Date(e.target.value) })
                }
              />
              <span>to</span>
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
                COVID Period
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
          {metricsLoading ? (
            <div className="loading">Loading metrics...</div>
          ) : metrics ? (
            <>
              {/* Time Series Chart */}
              <div className="chart-card">
                <div className="chart-card-header">
                  <h3>Activity Over Time</h3>
                  <span className="chart-subtitle">Monthly averages</span>
                </div>
                <TimeSeriesChart
                  data={metrics.metrics}
                  selectedMetrics={selectedMetrics}
                  width={700}
                  height={300}
                />
              </div>

              {/* Seasonal Comparison */}
              {metrics.seasonal_summary && (
                <div className="chart-card">
                  <div className="chart-card-header">
                    <h3>Seasonal Comparison</h3>
                    <span className="chart-subtitle">Winter vs Summer</span>
                  </div>
                  <SeasonalBarChart data={metrics.seasonal_summary} width={600} height={300} />
                </div>
              )}

              {/* Summary Stats */}
              <div className="stats-grid">
                {selectedMetrics.map((metric) => {
                  const metricData = metrics.metrics[metric];
                  if (!metricData) return null;

                  const values = metricData.data.map((d) => d.value);
                  const avg = values.reduce((a, b) => a + b, 0) / values.length;
                  const min = Math.min(...values);
                  const max = Math.max(...values);

                  return (
                    <div key={metric} className={`stat-card metric-${metric}`}>
                      <h4>{METRIC_OPTIONS.find((o) => o.value === metric)?.label}</h4>
                      <div className="stat-value">{avg.toFixed(3)}</div>
                      <div className="stat-label">Average ({metricData.unit})</div>
                      <div className="stat-range">
                        <span>Min: {min.toFixed(3)}</span>
                        <span>Max: {max.toFixed(3)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Seasonal Summary */}
              {metrics.seasonal_summary && (
                <div className="seasonal-summary">
                  <h3>Seasonal Patterns</h3>
                  <div className="seasonal-grid">
                    {selectedMetrics.map((metric) => {
                      const change = metrics.seasonal_summary?.change_pct[metric];
                      if (change === null || change === undefined) return null;

                      return (
                        <div key={metric} className="seasonal-item">
                          <span className="metric-name">
                            {METRIC_OPTIONS.find((o) => o.value === metric)?.label}
                          </span>
                          <span
                            className={`change-value ${change > 0 ? 'positive' : change < 0 ? 'negative' : ''}`}
                          >
                            {change > 0 ? '+' : ''}
                            {change.toFixed(1)}%
                          </span>
                          <span className="change-label">Summer vs Winter</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="no-data">
              <p>No data available for this region and time period.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
