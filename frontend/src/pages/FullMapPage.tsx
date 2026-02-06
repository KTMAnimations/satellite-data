import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Map as LeafletMap } from 'leaflet';
import { MapView } from '../components/Map/MapContainer';
import { HeatmapLegend } from '../components/Map/HeatmapLegend';
import { TimeSlider } from '../components/Charts/TimeSlider';
import { useStore } from '../store';
import type { Granularity, MetricType } from '../types';
import {
  estimateBucketCount,
  getRecommendedGranularity,
  METRICS_MAX_TIMESERIES_POINTS_DEFAULT,
  METRIC_SUPPORTED_GRANULARITIES,
} from '../config/metrics';
import { formatDateYYYYMMDD, parseMetricDate } from '../utils/dates';
import './MapPage.css';

const METRIC_OPTIONS: { value: MetricType; label: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights' },
  { value: 'ndvi', label: 'NDVI (Vegetation)' },
  { value: 'urban_density', label: 'Urban Density' },
  { value: 'parking', label: 'Parking Occupancy' },
  { value: 'land_cover', label: 'Land Cover' },
  { value: 'surface_water', label: 'Surface Water' },
  { value: 'no2', label: 'NO₂ Pollution' },
  { value: 'temperature', label: 'Temperature' },
  { value: 'precipitation', label: 'Precipitation' },
  { value: 'aerosol', label: 'Aerosol Index' },
  { value: 'cropland', label: 'Cropland' },
  { value: 'evapotranspiration', label: 'Evapotranspiration' },
  { value: 'soil_moisture', label: 'Soil Moisture' },
  { value: 'impervious', label: 'Impervious Surface' },
  { value: 'canopy_height', label: 'Canopy Height' },
];

function toDateOnly(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function buildTimelineDates(start: Date, end: Date, granularity: Granularity): Date[] {
  const startDate = toDateOnly(start);
  const endDate = toDateOnly(end);
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return [];
  if (startDate.getTime() > endDate.getTime()) return [];

  const dates: Date[] = [];
  if (granularity === 'monthly') {
    let current = new Date(startDate.getFullYear(), startDate.getMonth(), 1);
    while (current.getTime() <= endDate.getTime()) {
      dates.push(new Date(current));
      current = new Date(current.getFullYear(), current.getMonth() + 1, 1);
    }
    return dates;
  }

  const stepDays = granularity === 'weekly' ? 7 : 1;
  const current = new Date(startDate);
  while (current.getTime() <= endDate.getTime()) {
    dates.push(new Date(current));
    current.setDate(current.getDate() + stepDays);
  }
  return dates;
}

export function FullMapPage() {
  const { dateRange, setDateRange } = useStore();
  const queryClient = useQueryClient();
  const fullscreenTargetRef = useRef<HTMLDivElement | null>(null);

  const [selectedMapMetric, setSelectedMapMetric] = useState<MetricType>('nightlights');
  const [selectedGranularity, setSelectedGranularity] = useState<Granularity | null>(null);
  const [overlayEnabled, setOverlayEnabled] = useState(true);
  const [isTimelinePlaying, setIsTimelinePlaying] = useState(false);
  const [currentTimelineDate, setCurrentTimelineDate] = useState<Date | null>(null);
  const [overlayIsLoading, setOverlayIsLoading] = useState(false);
  const [mapInstance, setMapInstance] = useState<LeafletMap | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const fullscreenEnabled = typeof document !== 'undefined' && document.fullscreenEnabled;

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

  const timelineDates = useMemo(
    () => buildTimelineDates(dateRange.start, dateRange.end, granularity),
    [dateRange.end, dateRange.start, granularity]
  );

  useEffect(() => {
    setCurrentTimelineDate(null);
    setIsTimelinePlaying(false);
    setSelectedGranularity(null);
  }, [selectedMapMetric]);

  useEffect(() => {
    if (timelineDates.length > 0) setCurrentTimelineDate(timelineDates[0]);
  }, [timelineDates]);

  const handleClearCache = () => {
    queryClient.resetQueries({ queryKey: ['tiles'] });
  };

  const handleToggleFullscreen = useCallback(async () => {
    const target = fullscreenTargetRef.current;
    if (!target) return;

    try {
      if (document.fullscreenElement && document.fullscreenElement !== target) {
        await document.exitFullscreen();
      }

      if (document.fullscreenElement === target) {
        await document.exitFullscreen();
        return;
      }

      await target.requestFullscreen();
    } catch (err) {
      console.warn('Failed to toggle fullscreen:', err);
    }
  }, []);

  useEffect(() => {
    if (!fullscreenEnabled) return;

    const handleFullscreenChange = () => {
      const target = fullscreenTargetRef.current;
      const nowFullscreen = Boolean(target && document.fullscreenElement === target);
      setIsFullscreen(nowFullscreen);

      if (mapInstance) {
        requestAnimationFrame(() => mapInstance.invalidateSize({ animate: false }));
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [fullscreenEnabled, mapInstance]);

  const tileDate =
    formatDateYYYYMMDD(currentTimelineDate)
    ?? formatDateYYYYMMDD(dateRange.start)
    ?? formatDateYYYYMMDD(new Date())
    ?? new Date().toISOString().split('T')[0];

  return (
    <div className="map-page">
      <div className="map-page-toolbar">
        <div className="map-page-toolbar-left">
          <div className="map-page-title-row">
            <span className="map-page-kicker">Full Map</span>
            <span className="map-page-title-sep">·</span>
            <div className="map-page-name">Global view</div>
          </div>

          <button
            type="button"
            className="btn btn-outline btn-icon map-page-cache-btn"
            onClick={handleClearCache}
            aria-label="Clear cached tiles"
            title="Clear cached tiles"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 10-3.1 6.7" />
              <path d="M21 12v7h-7" />
            </svg>
          </button>
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

          {supportedGranularities.length > 1 && (
            <div className="map-page-granularity">
              {supportedGranularities.map((g) => {
                const withinLimit =
                  estimateBucketCount(dateRange.start, dateRange.end, g) <= METRICS_MAX_TIMESERIES_POINTS_DEFAULT;
                const label = g.charAt(0).toUpperCase() + g.slice(1);

                return (
                  <button
                    key={g}
                    type="button"
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

          <div className="map-page-overlay-controls">
            <button
              type="button"
              className="btn btn-outline map-page-overlay-toggle"
              onClick={() => setOverlayEnabled((prev) => !prev)}
              aria-pressed={overlayEnabled}
              aria-label={overlayEnabled ? 'Hide overlay' : 'Show overlay'}
              title={overlayEnabled ? 'Hide overlay' : 'Show overlay'}
            >
              Overlay {overlayEnabled ? 'On' : 'Off'}
            </button>
          </div>

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
        <div className="map-page-map" ref={fullscreenTargetRef}>
          <MapView
            regions={[]}
            selectedMetric={selectedMapMetric}
            overlayEnabled={overlayEnabled}
            tileGranularity={granularity}
            tileDate={tileDate}
            onOverlayLoadingChange={setOverlayIsLoading}
            onMapReady={setMapInstance}
            selectedRegion={null}
          />

          {fullscreenEnabled && (
            <button
              type="button"
              className="btn btn-outline btn-icon map-page-fullscreen-btn"
              onClick={handleToggleFullscreen}
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            >
              {isFullscreen ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 9h5V4" />
                  <path d="M21 9h-5V4" />
                  <path d="M3 15h5v5" />
                  <path d="M21 15h-5v5" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M8 3H3v5" />
                  <path d="M16 3h5v5" />
                  <path d="M8 21H3v-5" />
                  <path d="M16 21h5v-5" />
                </svg>
              )}
            </button>
          )}

          {overlayEnabled && (
            <div className="map-page-legend">
              <HeatmapLegend
                metric={selectedMapMetric}
                showValues={false}
                tileDate={tileDate}
                tileGranularity={granularity}
              />
            </div>
          )}
        </div>

        <div className="map-page-timeline">
          {timelineDates.length > 0 && currentTimelineDate ? (
            <TimeSlider
              dates={timelineDates}
              selectedDate={currentTimelineDate}
              onDateChange={setCurrentTimelineDate}
              isPlaying={isTimelinePlaying}
              playbackBlocked={overlayIsLoading}
              onPlayPause={() => setIsTimelinePlaying(!isTimelinePlaying)}
              density="compact"
              width={720}
            />
          ) : (
            <div className="map-page-hint">Select a valid date range to view the timeline.</div>
          )}
        </div>
      </div>
    </div>
  );
}
