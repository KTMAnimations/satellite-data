import { useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { SplitScreenCompare } from '../components/Map/SplitScreenCompare';
import api from '../services/api';
import type { MetricType } from '../types';
import './CompareView.css';

const METRIC_OPTIONS: { value: MetricType; label: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights' },
  { value: 'ndvi', label: 'NDVI (Vegetation)' },
  { value: 'urban_density', label: 'Urban Density' },
  { value: 'parking', label: 'Parking Occupancy' },
];

const PRESET_COMPARISONS = [
  {
    label: 'Winter vs Summer',
    periodA: { start: '2023-12-01', end: '2024-02-28' },
    periodB: { start: '2023-06-01', end: '2023-08-31' },
  },
  {
    label: 'COVID Impact',
    periodA: { start: '2019-01-01', end: '2019-12-31' },
    periodB: { start: '2020-01-01', end: '2020-12-31' },
  },
  {
    label: 'Year over Year',
    periodA: { start: '2023-01-01', end: '2023-12-31' },
    periodB: { start: '2024-01-01', end: '2024-12-31' },
  },
];

export function CompareView() {
  const { regionId } = useParams<{ regionId: string }>();
  const [selectedMetric, setSelectedMetric] = useState<MetricType>('nightlights');
  const [periodA, setPeriodA] = useState({
    start: '2023-12-01',
    end: '2024-02-28',
  });
  const [periodB, setPeriodB] = useState({
    start: '2023-06-01',
    end: '2023-08-31',
  });

  const { data: region } = useQuery({
    queryKey: ['region', regionId],
    queryFn: () => api.getRegion(regionId!),
    enabled: !!regionId,
  });

  const { data: comparison } = useQuery({
    queryKey: ['comparison', regionId, periodA, periodB, selectedMetric],
    queryFn: () =>
      api.comparePeriods({
        region_id: regionId!,
        period_a_start: periodA.start,
        period_a_end: periodA.end,
        period_b_start: periodB.start,
        period_b_end: periodB.end,
        metrics: [selectedMetric],
      }),
    enabled: !!regionId,
  });

  const changePercent = useMemo(() => {
    if (!comparison?.change?.[selectedMetric]) return null;
    return comparison.change[selectedMetric];
  }, [comparison, selectedMetric]);

  const applyPreset = (preset: typeof PRESET_COMPARISONS[0]) => {
    setPeriodA({ start: preset.periodA.start, end: preset.periodA.end });
    setPeriodB({ start: preset.periodB.start, end: preset.periodB.end });
  };

  if (!regionId) {
    return (
      <div className="compare-view">
        <div className="no-region">
          <h2>No Region Selected</h2>
          <p>Select a region to compare time periods.</p>
          <Link to="/regions" className="btn btn-primary">
            Go to Region Explorer
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="compare-view">
      {/* Header */}
      <header className="compare-header">
        <div className="header-left">
          <Link to={`/analysis/${regionId}`} className="back-link">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Back to Analysis
          </Link>
          <div className="header-title">
            <h1>Temporal Comparison</h1>
            {region && <span className="region-name">{region.name}</span>}
          </div>
        </div>

        <div className="header-actions">
          <select
            value={selectedMetric}
            onChange={(e) => setSelectedMetric(e.target.value as MetricType)}
            className="metric-select"
          >
            {METRIC_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="compare-content">
        {/* Controls */}
        <aside className="compare-sidebar">
          {/* Presets */}
          <section className="control-section">
            <h4>Quick Presets</h4>
            <div className="preset-buttons">
              {PRESET_COMPARISONS.map((preset) => (
                <button
                  key={preset.label}
                  className="btn btn-secondary preset-btn"
                  onClick={() => applyPreset(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </section>

          {/* Period A */}
          <section className="control-section">
            <h4>Period A (Before)</h4>
            <div className="period-inputs">
              <div className="date-field">
                <label>Start</label>
                <input
                  type="date"
                  value={periodA.start}
                  onChange={(e) => setPeriodA({ ...periodA, start: e.target.value })}
                />
              </div>
              <div className="date-field">
                <label>End</label>
                <input
                  type="date"
                  value={periodA.end}
                  onChange={(e) => setPeriodA({ ...periodA, end: e.target.value })}
                />
              </div>
            </div>
          </section>

          {/* Period B */}
          <section className="control-section">
            <h4>Period B (After)</h4>
            <div className="period-inputs">
              <div className="date-field">
                <label>Start</label>
                <input
                  type="date"
                  value={periodB.start}
                  onChange={(e) => setPeriodB({ ...periodB, start: e.target.value })}
                />
              </div>
              <div className="date-field">
                <label>End</label>
                <input
                  type="date"
                  value={periodB.end}
                  onChange={(e) => setPeriodB({ ...periodB, end: e.target.value })}
                />
              </div>
            </div>
          </section>

          {/* Results */}
          {comparison && (
            <section className="control-section results-section">
              <h4>Comparison Results</h4>
              <div className="results-card">
                <div className="result-metric">
                  <span className="metric-label">
                    {METRIC_OPTIONS.find((o) => o.value === selectedMetric)?.label}
                  </span>
                </div>

                <div className="result-values">
                  <div className="value-item">
                    <span className="label">Period A Avg</span>
                    <span className="value mono">
                      {comparison.period_a.averages[selectedMetric]?.toFixed(4) || 'N/A'}
                    </span>
                  </div>
                  <div className="value-item">
                    <span className="label">Period B Avg</span>
                    <span className="value mono">
                      {comparison.period_b.averages[selectedMetric]?.toFixed(4) || 'N/A'}
                    </span>
                  </div>
                </div>

                {changePercent !== null && (
                  <div className={`change-indicator ${changePercent >= 0 ? 'positive' : 'negative'}`}>
                    <span className="change-value">
                      {changePercent >= 0 ? '+' : ''}
                      {changePercent.toFixed(1)}%
                    </span>
                    <span className="change-label">Change</span>
                  </div>
                )}

                <div className="observation-counts">
                  <span>
                    Period A: {comparison.period_a.observation_count} observations
                  </span>
                  <span>
                    Period B: {comparison.period_b.observation_count} observations
                  </span>
                </div>
              </div>
            </section>
          )}
        </aside>

        {/* Main - Map Comparison */}
        <main className="compare-main">
          {region ? (
            <div className="split-map-container">
              <SplitScreenCompare
                region={region}
                metric={selectedMetric}
                dateA={periodA.start}
                dateB={periodB.start}
                labelA="Period A"
                labelB="Period B"
              />
            </div>
          ) : (
            <div className="loading">Loading region...</div>
          )}

          {/* Bar Chart Comparison */}
          {comparison && (
            <div className="comparison-chart card">
              <h3>Period Comparison</h3>
              <div className="bar-comparison">
                <div className="bar-group">
                  <div className="bar-label">
                    <span>Period A</span>
                    <span className="mono">{periodA.start} to {periodA.end}</span>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill period-a"
                      style={{
                        width: `${
                          comparison.period_a.averages[selectedMetric]
                            ? Math.min(
                                100,
                                (comparison.period_a.averages[selectedMetric] /
                                  Math.max(
                                    comparison.period_a.averages[selectedMetric],
                                    comparison.period_b.averages[selectedMetric]
                                  )) *
                                  100
                              )
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                  <span className="bar-value mono">
                    {comparison.period_a.averages[selectedMetric]?.toFixed(3) || 'N/A'}
                  </span>
                </div>

                <div className="bar-group">
                  <div className="bar-label">
                    <span>Period B</span>
                    <span className="mono">{periodB.start} to {periodB.end}</span>
                  </div>
                  <div className="bar-track">
                    <div
                      className="bar-fill period-b"
                      style={{
                        width: `${
                          comparison.period_b.averages[selectedMetric]
                            ? Math.min(
                                100,
                                (comparison.period_b.averages[selectedMetric] /
                                  Math.max(
                                    comparison.period_a.averages[selectedMetric],
                                    comparison.period_b.averages[selectedMetric]
                                  )) *
                                  100
                              )
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                  <span className="bar-value mono">
                    {comparison.period_b.averages[selectedMetric]?.toFixed(3) || 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
