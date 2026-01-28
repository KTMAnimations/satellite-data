import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { MapView } from '../components/Map/MapContainer';
import { HeatmapLegend } from '../components/Map/HeatmapLegend';
import { TimeSlider } from '../components/Charts/TimeSlider';
import { useStore } from '../store';
import api from '../services/api';
import type { MetricType } from '../types';
import { METRIC_DEFAULT_GRANULARITY } from '../config/metrics';
import { formatDateYYYYMMDD, parseMetricDate } from '../utils/dates';
import { formatApiError } from '../utils/errors';
import './MapPage.css';

const METRIC_OPTIONS: { value: MetricType; label: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights' },
  { value: 'ndvi', label: 'NDVI (Vegetation)' },
  { value: 'urban_density', label: 'Urban Density' },
  { value: 'parking', label: 'Parking Occupancy' },
  { value: 'land_cover', label: 'Land Cover' },
  { value: 'surface_water', label: 'Surface Water' },
  { value: 'active_fire', label: 'Active Fire' },
  { value: 'no2', label: 'NO₂ Pollution' },
  { value: 'temperature', label: 'Temperature' },
  { value: 'precipitation', label: 'Precipitation' },
  { value: 'aerosol', label: 'Aerosol Index' },
  { value: 'cropland', label: 'Cropland' },
  { value: 'evapotranspiration', label: 'Evapotranspiration' },
  { value: 'soil_moisture', label: 'Soil Moisture' },
  { value: 'impervious', label: 'Impervious Surface' },
  { value: 'fire_historical', label: 'Historical Fire' },
  { value: 'canopy_height', label: 'Canopy Height' },
];

export function MapPage() {
  const { regionId } = useParams<{ regionId: string }>();
  const { dateRange, setDateRange } = useStore();

  const [selectedMapMetric, setSelectedMapMetric] = useState<MetricType>('nightlights');
  const [isTimelinePlaying, setIsTimelinePlaying] = useState(false);
  const [currentTimelineDate, setCurrentTimelineDate] = useState<Date | null>(null);

  const { data: region, isError: regionIsError, error: regionError } = useQuery({
    queryKey: ['region', regionId],
    queryFn: () => api.getRegion(regionId!),
    enabled: !!regionId,
  });

  const granularity = METRIC_DEFAULT_GRANULARITY[selectedMapMetric];

  const {
    data: metrics,
    isLoading: metricsLoading,
    isError: metricsIsError,
    error: metricsError,
  } = useQuery({
    queryKey: ['metrics', regionId, granularity, dateRange, selectedMapMetric],
    queryFn: () =>
      api.getMetrics(regionId!, {
        start_date: formatDateYYYYMMDD(dateRange.start) ?? dateRange.start.toISOString().split('T')[0],
        end_date: formatDateYYYYMMDD(dateRange.end) ?? dateRange.end.toISOString().split('T')[0],
        metrics: [selectedMapMetric],
        granularity,
      }),
    enabled: !!regionId,
  });

  const timelineDates = useMemo(() => {
    const series = metrics?.metrics[selectedMapMetric]?.data;
    if (!series) return [];
    return series
      .map((d) => parseMetricDate(d.date))
      .flatMap((d) => (d && !Number.isNaN(d.getTime()) ? [d] : []))
      .sort((a, b) => a.getTime() - b.getTime())
      .filter((d, i, arr) => i === 0 || d.getTime() !== arr[i - 1].getTime());
  }, [metrics, selectedMapMetric]);

  useEffect(() => {
    setCurrentTimelineDate(null);
    setIsTimelinePlaying(false);
  }, [selectedMapMetric]);

  useEffect(() => {
    if (timelineDates.length > 0) setCurrentTimelineDate(timelineDates[0]);
  }, [timelineDates]);

  if (!regionId) {
    return (
      <div className="map-page">
        <div className="map-page-empty">
          <h2>No Region Selected</h2>
          <p>Select a region to view the full map.</p>
          <Link to="/regions" className="btn btn-primary">Explore Regions</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="map-page">
      <div className="map-page-toolbar">
        <div className="map-page-toolbar-left">
          <Link to={`/analysis/${regionId}`} className="btn btn-outline">Back to Analysis</Link>
          <div className="map-page-title">
            <div className="map-page-kicker">Full Map</div>
            <div className="map-page-name">
              {regionIsError ? `Error: ${formatApiError(regionError)}` : (region?.name ?? 'Loading…')}
            </div>
          </div>
        </div>

        <div className="map-page-toolbar-right">
          <select
            value={selectedMapMetric}
            onChange={(e) => setSelectedMapMetric(e.target.value as MetricType)}
            className="metric-select"
            aria-label="Metric"
          >
            {METRIC_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <div className="map-page-dates">
            <input
              type="date"
              value={formatDateYYYYMMDD(dateRange.start) ?? dateRange.start.toISOString().split('T')[0]}
              onChange={(e) =>
                setDateRange({ ...dateRange, start: parseMetricDate(e.target.value) ?? new Date(e.target.value) })
              }
            />
            <span className="map-page-date-sep">to</span>
            <input
              type="date"
              value={formatDateYYYYMMDD(dateRange.end) ?? dateRange.end.toISOString().split('T')[0]}
              onChange={(e) =>
                setDateRange({ ...dateRange, end: parseMetricDate(e.target.value) ?? new Date(e.target.value) })
              }
            />
          </div>
        </div>
      </div>

      <div className="map-page-body">
        <div className="map-page-map">
          {region && (
            <MapView
              regions={[region]}
              selectedMetric={selectedMapMetric}
              tileGranularity={granularity}
              tileDate={
                formatDateYYYYMMDD(currentTimelineDate)
                  ?? formatDateYYYYMMDD(dateRange.start)
                  ?? formatDateYYYYMMDD(new Date())
                  ?? new Date().toISOString().split('T')[0]
              }
            />
          )}

          <div className="map-page-legend">
            <HeatmapLegend metric={selectedMapMetric} showValues={false} />
          </div>
        </div>

        <div className="map-page-timeline">
          {metricsLoading ? (
            <div className="map-page-hint">Loading timeline…</div>
          ) : metricsIsError ? (
            <div className="map-page-hint">Failed to load timeline: {formatApiError(metricsError)}</div>
          ) : timelineDates.length > 0 && currentTimelineDate ? (
            <TimeSlider
              dates={timelineDates}
              selectedDate={currentTimelineDate}
              onDateChange={setCurrentTimelineDate}
              isPlaying={isTimelinePlaying}
              onPlayPause={() => setIsTimelinePlaying(!isTimelinePlaying)}
              width={720}
            />
          ) : (
            <div className="map-page-hint">No timeline data available for this metric/date range.</div>
          )}
        </div>
      </div>
    </div>
  );
}

