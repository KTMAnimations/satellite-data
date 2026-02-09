import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import type { Map as LeafletMap } from 'leaflet';
import {
  FilePdf,
  Table,
  FilmStrip,
  DownloadSimple,
  Clock,
  CheckCircle,
  Spinner,
  WarningCircle,
} from '@phosphor-icons/react';
import { MapView } from '../components/Map/MapContainer';
import { TimeSlider } from '../components/Charts/TimeSlider';
import api from '../services/api';
import { useStore } from '../store';
import { formatApiError } from '../utils/errors';
import { formatDateTimeInClientTimeZone } from '../utils/dateTime';
import { formatDateYYYYMMDD, parseMetricDate } from '../utils/dates';
import type { Granularity, MetricType, Region } from '../types';
import { METRIC_OPTIONS, METRIC_SUPPORTED_GRANULARITIES } from '../config/metrics';
import './ExportCenter.css';

function getAnimationGranularity(metric: MetricType, startDate: string, endDate: string): Granularity {
  const supportsDaily = METRIC_SUPPORTED_GRANULARITIES[metric]?.includes('daily');
  if (!supportsDaily) return 'monthly';

  const start = new Date(startDate);
  const end = new Date(endDate);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) {
    return 'monthly';
  }

  const msPerDay = 1000 * 60 * 60 * 24;
  const days = Math.floor((end.getTime() - start.getTime()) / msPerDay);
  return days <= 90 ? 'daily' : 'monthly';
}

export function ExportCenter() {
  const [searchParams] = useSearchParams();
  const defaultRegionId = searchParams.get('region') || '';

  const [selectedRegionId, setSelectedRegionId] = useState(defaultRegionId);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'csv' | 'animation'>('pdf');
  const [selectedMetrics, setSelectedMetrics] = useState<MetricType[]>(['nightlights', 'ndvi']);
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate] = useState('2023-12-31');
  const [animationMetric, setAnimationMetric] = useState<MetricType>('nightlights');
  const [animationFormat, setAnimationFormat] = useState<'gif'>('gif');
  const [animationIncludeBasemap, setAnimationIncludeBasemap] = useState(true);
  const [animationOverlayOpacity, setAnimationOverlayOpacity] = useState(0.7);
  const [previewDate, setPreviewDate] = useState<Date | null>(null);
  const [previewIsPlaying, setPreviewIsPlaying] = useState(false);
  const [previewPlaybackSpeed, setPreviewPlaybackSpeed] = useState(1);
  const [previewOverlayIsLoading, setPreviewOverlayIsLoading] = useState(false);
  const [animationViewportBounds, setAnimationViewportBounds] = useState<
    [number, number, number, number] | null
  >(null);
  const [previewTimelineWidth, setPreviewTimelineWidth] = useState(560);
  const exportQueue = useStore((state) => state.exportQueue);
  const addExportToQueue = useStore((state) => state.addExportToQueue);
  const setExportQueue = useStore((state) => state.setExportQueue);
  const previewMapCleanupRef = useRef<(() => void) | null>(null);

  const { data: regionsData, isLoading: regionsLoading, isError: regionsIsError, error: regionsError } = useQuery({
    queryKey: ['regions', { page_size: 100 }],
    queryFn: ({ signal }) => api.listRegions({ page_size: 100 }, { signal }),
  });

  const selectedRegion = useMemo<Region | null>(
    () => regionsData?.regions.find((region) => region.id === selectedRegionId) ?? null,
    [regionsData?.regions, selectedRegionId]
  );

  const animationGranularity = useMemo(
    () => getAnimationGranularity(animationMetric, startDate, endDate),
    [animationMetric, startDate, endDate]
  );

  const { data: animationMetricsData } = useQuery({
    queryKey: [
      'animation-preview-metrics',
      selectedRegionId,
      animationMetric,
      animationGranularity,
      startDate,
      endDate,
    ],
    queryFn: ({ signal }) =>
      api.getMetrics(
        selectedRegionId,
        {
          start_date: startDate,
          end_date: endDate,
          metrics: [animationMetric],
          granularity: animationGranularity,
        },
        { signal }
      ),
    enabled:
      exportFormat === 'animation' &&
      animationFormat === 'gif' &&
      Boolean(selectedRegionId) &&
      Boolean(startDate) &&
      Boolean(endDate),
  });

  const animationDates = useMemo(() => {
    const points = animationMetricsData?.metrics?.[animationMetric]?.data;
    if (!points) return [];
    return points
      .map((point) => parseMetricDate(point.date))
      .flatMap((date) => (date && !Number.isNaN(date.getTime()) ? [date] : []))
      .sort((a, b) => a.getTime() - b.getTime());
  }, [animationMetricsData, animationMetric]);

  const previewAspectRatio = '4 / 3';

  const updateViewportBounds = useCallback((map: LeafletMap | null) => {
    if (!map) return;
    const bounds = map.getBounds();
    const next: [number, number, number, number] = [
      bounds.getWest(),
      bounds.getSouth(),
      bounds.getEast(),
      bounds.getNorth(),
    ];
    setAnimationViewportBounds(next);
  }, []);

  const handlePreviewMapReady = useCallback(
    (map: LeafletMap | null) => {
      previewMapCleanupRef.current?.();
      previewMapCleanupRef.current = null;

      if (!map) {
        setAnimationViewportBounds(null);
        return;
      }

      const syncBounds = () => updateViewportBounds(map);
      syncBounds();
      map.on('moveend', syncBounds);
      map.on('zoomend', syncBounds);
      previewMapCleanupRef.current = () => {
        map.off('moveend', syncBounds);
        map.off('zoomend', syncBounds);
      };
    },
    [updateViewportBounds]
  );

  const pdfMutation = useMutation({
    mutationFn: () =>
      api.exportPdf({
        region_id: selectedRegionId,
        format: 'pdf',
        start_date: startDate,
        end_date: endDate,
        metrics: selectedMetrics,
        include_charts: true,
        include_maps: true,
      }),
    onSuccess: (data) => addExportToQueue(data),
  });

  const csvMutation = useMutation({
    mutationFn: () =>
      api.exportCsv({
        region_ids: selectedRegionId ? [selectedRegionId] : undefined,
        metrics: selectedMetrics,
        start_date: startDate,
        end_date: endDate,
      }),
    onSuccess: (data) => addExportToQueue(data),
  });

  const animationMutation = useMutation({
    mutationFn: () =>
      api.exportAnimation({
        region_id: selectedRegionId,
        metric: animationMetric,
        format: animationFormat,
        include_basemap: animationIncludeBasemap,
        overlay_opacity: animationOverlayOpacity,
        start_date: startDate,
        end_date: endDate,
        frame_duration_ms: 500,
        viewport_bounds: animationViewportBounds ?? undefined,
      }),
    onSuccess: (data) => addExportToQueue(data),
  });

  // Poll for export status updates
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Check if any exports are pending or processing
    const pendingExports = exportQueue.filter(
      (exp) => exp.status === 'pending' || exp.status === 'processing'
    );

    if (pendingExports.length > 0) {
      // Start polling
      pollIntervalRef.current = setInterval(async () => {
        const updatedExports = await Promise.all(
          exportQueue.map(async (exp) => {
            if (exp.status === 'pending' || exp.status === 'processing') {
              try {
                const updated = await api.getExportStatus(exp.id);
                return updated;
              } catch {
                return exp;
              }
            }
            return exp;
          })
        );
        setExportQueue(updatedExports);
      }, 2000); // Poll every 2 seconds
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [exportQueue, setExportQueue]);

  useEffect(() => {
    const updateTimelineWidth = () => {
      const next = Math.max(260, Math.min(560, window.innerWidth - 420));
      setPreviewTimelineWidth(next);
    };
    updateTimelineWidth();
    window.addEventListener('resize', updateTimelineWidth);
    return () => window.removeEventListener('resize', updateTimelineWidth);
  }, []);

  useEffect(() => {
    setPreviewDate((current) => {
      if (animationDates.length === 0) return null;
      if (!current) return animationDates[0];
      const existing = animationDates.find((date) => date.getTime() === current.getTime());
      return existing ?? animationDates[0];
    });
    if (animationDates.length === 0) {
      setPreviewIsPlaying(false);
    }
  }, [animationDates]);

  useEffect(() => {
    if (exportFormat !== 'animation' || animationFormat !== 'gif') {
      setPreviewIsPlaying(false);
    }
  }, [animationFormat, exportFormat]);

  useEffect(
    () => () => {
      previewMapCleanupRef.current?.();
      previewMapCleanupRef.current = null;
    },
    []
  );

  const handleExport = () => {
    if (!selectedRegionId) {
      alert('Please select a region to continue.');
      return;
    }

    switch (exportFormat) {
      case 'pdf':
        pdfMutation.mutate();
        break;
      case 'csv':
        csvMutation.mutate();
        break;
      case 'animation':
        animationMutation.mutate();
        break;
    }
  };

  const toggleMetric = (metric: MetricType) => {
    setSelectedMetrics((prev) =>
      prev.includes(metric) ? prev.filter((m) => m !== metric) : [...prev, metric]
    );
  };

  const handlePreviewDateChange = (date: Date) => {
    setPreviewDate(date);
  };

  const handlePreviewPlayPause = () => {
    if (animationDates.length === 0) return;
    setPreviewIsPlaying((current) => !current);
  };

  const previewTileDate = previewDate && !Number.isNaN(previewDate.getTime())
    ? (formatDateYYYYMMDD(previewDate) ?? previewDate.toISOString().split('T')[0])
    : undefined;
  const previewDateLabelOptions: Intl.DateTimeFormatOptions =
    animationGranularity === 'monthly'
      ? { year: 'numeric', month: 'short' }
      : { year: 'numeric', month: 'short', day: '2-digit' };

  return (
    <div className="export-center">
      <header className="export-header">
        <h1>Export Center</h1>
        <p>Generate reports, download data, or create animations</p>
      </header>

      <div className="export-content">
        {/* Export Configuration */}
        <div className="export-config card">
          <h2>Export Configuration</h2>

          {/* Region Selection */}
          <div className="form-group">
            <label>Region</label>
            <select
              value={selectedRegionId}
              onChange={(e) => setSelectedRegionId(e.target.value)}
              className="form-select"
              disabled={regionsLoading || regionsIsError}
            >
              <option value="">
                {regionsLoading
                  ? 'Loading regions...'
                  : regionsIsError
                    ? `Error loading regions: ${formatApiError(regionsError)}`
                    : 'Select a region...'}
              </option>
              {!regionsIsError && regionsData?.regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </div>

          {/* Export Format */}
          <div className="form-group">
            <label>Export Format</label>
            <div className="format-options">
              <button
                className={`format-btn ${exportFormat === 'animation' ? 'active' : ''}`}
                onClick={() => setExportFormat('animation')}
              >
                <FilmStrip size={24} weight="duotone" className="format-icon" />
                <span>Animation</span>
              </button>
              <button
                className={`format-btn ${exportFormat === 'pdf' ? 'active' : ''}`}
                onClick={() => setExportFormat('pdf')}
              >
                <FilePdf size={24} weight="duotone" className="format-icon" />
                <span>PDF Report</span>
              </button>
              <button
                className={`format-btn ${exportFormat === 'csv' ? 'active' : ''}`}
                onClick={() => setExportFormat('csv')}
              >
                <Table size={24} weight="duotone" className="format-icon" />
                <span>CSV Data</span>
              </button>
            </div>
          </div>

          {/* Date Range */}
          <div className="form-group">
            <label>Date Range</label>
            <div className="date-range">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
              <span>to</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* Metrics (for PDF/CSV) */}
          {exportFormat !== 'animation' && (
            <div className="form-group">
              <label>Metrics to Include</label>
              <div className="metrics-checkboxes">
                {METRIC_OPTIONS.map((opt) => (
                  <label key={opt.value} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={selectedMetrics.includes(opt.value)}
                      onChange={() => toggleMetric(opt.value)}
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Animation Options */}
          {exportFormat === 'animation' && (
            <>
              <div className="form-group">
                <label>Metric to Animate</label>
                <select
                  value={animationMetric}
                  onChange={(e) => setAnimationMetric(e.target.value as MetricType)}
                  className="form-select"
                >
                  {METRIC_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Animation Format</label>
                <div className="radio-group">
                  <label>
                    <input
                      type="radio"
                      checked={animationFormat === 'gif'}
                      onChange={() => setAnimationFormat('gif')}
                    />
                    GIF
                  </label>
                </div>
              </div>
              <div className="form-group">
                <label className="checkbox-label checkbox-label-inline">
                  <input
                    type="checkbox"
                    checked={animationIncludeBasemap}
                    onChange={(e) => setAnimationIncludeBasemap(e.target.checked)}
                  />
                  Include background map
                </label>
              </div>
              <div className="form-group">
                <label>Overlay Opacity: {Math.round(animationOverlayOpacity * 100)}%</label>
                <input
                  type="range"
                  min="0.1"
                  max="1"
                  step="0.05"
                  value={animationOverlayOpacity}
                  disabled={!animationIncludeBasemap}
                  onChange={(e) => setAnimationOverlayOpacity(Number(e.target.value))}
                />
              </div>

              {animationFormat === 'gif' && (
                <section className="gif-preview-panel" aria-label="GIF preview">
                  <div className="gif-preview-header">
                    <h3>GIF Preview</h3>
                    <p>Pan and zoom this map to choose exactly what the exported GIF shows.</p>
                  </div>

                  {!selectedRegion ? (
                    <p className="gif-preview-empty">Select a region to preview the export viewport.</p>
                  ) : (
                    <>
                      <div className="gif-preview-meta">
                        <span>
                          {previewDate && !Number.isNaN(previewDate.getTime())
                            ? `Frame: ${previewDate.toLocaleDateString('en-US', previewDateLabelOptions)}`
                            : 'Frame: loading...'}
                        </span>
                        <span>{animationGranularity === 'daily' ? 'Daily timeline' : 'Monthly timeline'}</span>
                        <span>{animationViewportBounds ? 'Viewport synced to export' : 'Move map to set viewport'}</span>
                      </div>

                      <div className="gif-preview-map" style={{ aspectRatio: previewAspectRatio }}>
                        <MapView
                          regions={[selectedRegion]}
                          selectedRegion={selectedRegion}
                          selectedMetric={animationMetric}
                          tileDate={previewTileDate}
                          tileGranularity={animationGranularity}
                          overlayEnabled={Boolean(previewTileDate)}
                          onOverlayLoadingChange={setPreviewOverlayIsLoading}
                          onMapReady={handlePreviewMapReady}
                        />
                      </div>

                      {animationDates.length > 0 ? (
                        <div className="gif-preview-timeline">
                          <TimeSlider
                            dates={animationDates}
                            selectedDate={previewDate ?? animationDates[0]}
                            onDateChange={handlePreviewDateChange}
                            isPlaying={previewIsPlaying}
                            onPlayPause={handlePreviewPlayPause}
                            playbackBlocked={previewOverlayIsLoading}
                            playbackSpeed={previewPlaybackSpeed}
                            onSpeedChange={setPreviewPlaybackSpeed}
                            width={previewTimelineWidth}
                            density="compact"
                          />
                        </div>
                      ) : (
                        <p className="gif-preview-empty">
                          No timeline data available for this metric/date range.
                        </p>
                      )}
                    </>
                  )}
                </section>
              )}
            </>
          )}

          <button
            className="btn btn-primary export-btn"
            onClick={handleExport}
            disabled={
              !selectedRegionId ||
              pdfMutation.isPending ||
              csvMutation.isPending ||
              animationMutation.isPending
            }
          >
            {pdfMutation.isPending || csvMutation.isPending || animationMutation.isPending
              ? 'Generating...'
              : `Generate ${exportFormat === 'animation' ? 'Animation' : exportFormat.toUpperCase()}`}
          </button>
        </div>

        {/* Export History */}
        <div className="export-history card">
          <h2>Recent Exports</h2>
          {exportQueue.length === 0 ? (
            <p className="no-exports">No exports yet. Generate one above!</p>
          ) : (
            <div className="export-list">
              {exportQueue.map((exp) => {
                const isAnimation = exp.format === 'gif';
                const progress = typeof exp.progress === 'number' ? exp.progress : 0;
                const clampedProgress = Math.min(100, Math.max(0, progress));
                const showProgress = exp.status === 'pending' || exp.status === 'processing';

                return (
                  <div key={exp.id} className="export-item instrument-panel">
                    <span className="bracket-bl" />
                    <span className="bracket-br" />
                    <div className="export-details">
                      <div className="export-info">
                        <span className="export-format">
                          {exp.format === 'pdf' && <FilePdf size={16} weight="duotone" />}
                          {exp.format === 'csv' && <Table size={16} weight="duotone" />}
                          {isAnimation && <FilmStrip size={16} weight="duotone" />}
                          {exp.format.toUpperCase()}
                        </span>
                        <span className={`export-status ${exp.status}`}>
                          {exp.status === 'pending' && <Clock size={14} />}
                          {exp.status === 'processing' && <Spinner size={14} className="spinning" />}
                          {exp.status === 'completed' && <CheckCircle size={14} />}
                          {exp.status === 'failed' && <WarningCircle size={14} />}
                          {exp.status}
                        </span>
                      </div>
                      <div className="export-meta">
                        <span>Started: {formatDateTimeInClientTimeZone(exp.created_at)}</span>
                        {exp.status === 'completed' && exp.completed_at && (
                          <span>Completed: {formatDateTimeInClientTimeZone(exp.completed_at)}</span>
                        )}
                        {exp.status !== 'completed' && exp.message && (
                          <span className="export-message">{exp.message}</span>
                        )}
                        {exp.status === 'failed' && exp.error && (
                          <span className="export-error">{exp.error}</span>
                        )}
                        {showProgress && (
                          <div className="export-progress" aria-label="Export progress">
                            <div
                              className={`export-progress-bar ${
                                exp.status === 'pending' ? 'indeterminate' : ''
                              }`}
                              style={
                                exp.status === 'pending'
                                  ? undefined
                                  : { width: `${clampedProgress}%` }
                              }
                            />
                          </div>
                        )}
                      </div>
                    </div>
                    {exp.status === 'completed' && exp.download_url && (
                      <a
                        href={api.getExportDownloadUrl(exp.id)}
                        className="btn btn-outline btn-sm"
                        download
                      >
                        <DownloadSimple size={14} />
                        Download
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
