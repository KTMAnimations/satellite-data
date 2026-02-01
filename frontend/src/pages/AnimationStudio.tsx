import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  DownloadSimple,
  Image,
} from '@phosphor-icons/react';
import { MapView } from '../components/Map/MapContainer';
import { TimeSlider } from '../components/Charts/TimeSlider';
import api from '../services/api';
import type { Granularity, Region, MetricType } from '../types';
import {
  estimateBucketCount,
  getRecommendedGranularity,
  METRICS_MAX_TIMESERIES_POINTS_DEFAULT,
  METRIC_SUPPORTED_GRANULARITIES,
} from '../config/metrics';
import { formatDateYYYYMMDD, parseMetricDate } from '../utils/dates';
import { formatApiError } from '../utils/errors';
import './AnimationStudio.css';

function formatGranularityLabel(granularity: string): string {
  return granularity ? `${granularity.slice(0, 1).toUpperCase()}${granularity.slice(1)}` : granularity;
}

const METRIC_OPTIONS: { value: MetricType; label: string; description: string }[] = [
  // Original metrics
  { value: 'nightlights', label: 'Nighttime Lights', description: 'Urban activity proxy (daily available)' },
  { value: 'ndvi', label: 'NDVI', description: 'Vegetation index showing greenness' },
  { value: 'urban_density', label: 'Urban Density', description: 'Built-up area estimation' },
  { value: 'parking', label: 'Parking Occupancy', description: 'Parking lot fill levels' },
  // Phase 1: Core datasets
  { value: 'land_cover', label: 'Land Cover', description: 'Dynamic World built-up probability' },
  { value: 'surface_water', label: 'Surface Water', description: 'JRC water extent mapping' },
  // Phase 2: Air quality & weather
  { value: 'no2', label: 'NO₂', description: 'Tropospheric nitrogen dioxide' },
  { value: 'temperature', label: 'Temperature', description: 'ERA5-Land 2m air temperature' },
  { value: 'precipitation', label: 'Precipitation', description: 'ERA5-Land total precipitation' },
  { value: 'aerosol', label: 'Aerosol', description: 'UV Aerosol Index (smoke/dust)' },
  // Phase 3: Agriculture
  { value: 'cropland', label: 'Cropland', description: 'ESA WorldCover cropland fraction' },
  { value: 'evapotranspiration', label: 'Evapotranspiration', description: 'OpenET water use' },
  { value: 'soil_moisture', label: 'Soil Moisture', description: 'SMAP root-zone moisture' },
  // Phase 4: Historical & specialized
  { value: 'impervious', label: 'Impervious Surface', description: 'GAIA urban expansion' },
  { value: 'canopy_height', label: 'Canopy Height', description: 'GEDI forest structure' },
];

const FORMAT_OPTIONS: Array<{ value: 'gif'; label: string; description: string }> = [
  { value: 'gif', label: 'GIF', description: 'Animated image, widely compatible' },
];

export function AnimationStudio() {
  const [selectedRegion, setSelectedRegion] = useState<Region | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<MetricType>('nightlights');
  const [selectedGranularity, setSelectedGranularity] = useState<Granularity | null>(null);
  const [dateRange, setDateRange] = useState({
    start: new Date(2023, 0, 1),   // Jan 1, 2023 - start of available data
    end: new Date(),               // Today - end of available data
  });
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentDate, setCurrentDate] = useState<Date>(dateRange.start);
  const [livePreview, setLivePreview] = useState(false);
  const [previewDate, setPreviewDate] = useState<Date | null>(null);
  const [previewOverlayIsLoading, setPreviewOverlayIsLoading] = useState(false);
  const [viewLocked, setViewLocked] = useState(false);
  const [exportFormat, setExportFormat] = useState<'gif'>('gif');
  const [frameDuration, setFrameDuration] = useState(500);
  const [resolution, setResolution] = useState({ width: 800, height: 600 });
  const [exportId, setExportId] = useState<string | null>(null);

  const previewRef = useRef<HTMLDivElement>(null);

  // Fetch regions
  const {
    data: regionsData,
    isLoading: regionsLoading,
    isError: regionsIsError,
    error: regionsError,
  } = useQuery({
    queryKey: ['regions', 'predefined'],
    queryFn: ({ signal }) => api.listRegions({ type: 'predefined', page_size: 50 }, { signal }),
  });

  // Keep metric/tile bucketing consistent with the Region "Full Map" view.
  const supportedGranularities = METRIC_SUPPORTED_GRANULARITIES[selectedMetric];
  const recommendedGranularity = getRecommendedGranularity(selectedMetric, dateRange);
  const selectedGranularityAllowed = Boolean(
    selectedGranularity
      && supportedGranularities.includes(selectedGranularity)
      && estimateBucketCount(dateRange.start, dateRange.end, selectedGranularity) <= METRICS_MAX_TIMESERIES_POINTS_DEFAULT
  );
  const granularity = selectedGranularityAllowed
    ? (selectedGranularity as Granularity)
    : recommendedGranularity;
  const { data: metrics } = useQuery({
    queryKey: ['metrics', selectedRegion?.id, selectedMetric, granularity, dateRange],
    queryFn: ({ signal }) =>
      api.getMetrics(selectedRegion!.id, {
        start_date: formatDateYYYYMMDD(dateRange.start) ?? dateRange.start.toISOString().split('T')[0],
        end_date: formatDateYYYYMMDD(dateRange.end) ?? dateRange.end.toISOString().split('T')[0],
        metrics: [selectedMetric],
        granularity,
      }, { signal }),
    enabled: !!selectedRegion,
  });

  // Generate date array from metrics - memoized to prevent infinite loops
  // Backend returns YYYY-MM format for monthly data
  const availableDates = useMemo(() => {
    const data = metrics?.metrics[selectedMetric]?.data;
    if (!data) return [];
    return data
      .map((d) => parseMetricDate(d.date))
      .flatMap((d) => (d && !Number.isNaN(d.getTime()) ? [d] : []));
  }, [metrics, selectedMetric]);

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: () =>
      api.exportAnimation({
        region_id: selectedRegion!.id,
        metric: selectedMetric,
        format: exportFormat,
        start_date: formatDateYYYYMMDD(dateRange.start) ?? dateRange.start.toISOString().split('T')[0],
        end_date: formatDateYYYYMMDD(dateRange.end) ?? dateRange.end.toISOString().split('T')[0],
        frame_duration_ms: frameDuration,
        width: resolution.width,
        height: resolution.height,
      }),
    onSuccess: (data) => {
      setExportId(data.id);
    },
  });

  // Poll export status
  const { data: exportStatus } = useQuery({
    queryKey: ['export-status', exportId],
    queryFn: ({ signal }) => api.getExportStatus(exportId!, { signal }),
    enabled: !!exportId && exportMutation.isSuccess,
    refetchInterval: (query) =>
      query.state.data?.status === 'completed' || query.state.data?.status === 'failed'
        ? false
        : 2000,
  });

  // Initialize current date when dates change or metric changes
  // Use JSON.stringify to create stable dependency (availableDates array is already memoized)
  const availableDatesKey = useMemo(
    () => availableDates.map(d => d.getTime()).join(','),
    [availableDates]
  );

  useEffect(() => {
    if (availableDates.length > 0) {
      // Find the first date that's within or after the selected date range
      const validDate = availableDates.find(d => d >= dateRange.start) || availableDates[0];
      setCurrentDate(validDate);
      setPreviewDate(validDate);
      return;
    } else {
      // Reset to date range start when no dates available (e.g., during metric switch)
      setCurrentDate(dateRange.start);
      setPreviewDate(dateRange.start);
    }
  }, [availableDatesKey, availableDates, dateRange.start, selectedMetric]);

  // Reset granularity when metric changes
  useEffect(() => {
    setSelectedGranularity(null);
  }, [selectedMetric]);

  // If preview is paused, ensure playback doesn't keep advancing dates invisibly.
  useEffect(() => {
    if (!livePreview && isPlaying) {
      setIsPlaying(false);
    }
  }, [livePreview, isPlaying]);

  const handleExport = () => {
    if (!selectedRegion) return;
    exportMutation.mutate();
  };

  const handleDownload = () => {
    if (exportStatus?.download_url) {
      window.open(api.getExportDownloadUrl(exportId!), '_blank');
    }
  };

  const isPreviewDirty = !previewDate || previewDate.getTime() !== currentDate.getTime();
  const dateLabelOptions: Intl.DateTimeFormatOptions =
    granularity === 'monthly'
      ? { year: 'numeric', month: 'long' }
      : { year: 'numeric', month: 'short', day: '2-digit' };

  const handleApplyPreview = () => {
    setPreviewDate(currentDate);
  };
  const handleToggleLivePreview = (next: boolean) => {
    setLivePreview(next);
    setPreviewDate(currentDate);
  };

  const handleToggleViewLock = (next: boolean) => {
    setViewLocked(next);
  };

  const handlePlayPause = () => {
    // Starting playback implies live updates (otherwise we'd spam-select dates without showing them).
    if (!isPlaying && !livePreview) {
      setLivePreview(true);
      setPreviewDate(currentDate);
    }
    setIsPlaying(!isPlaying);
  };

  const handleTimelineDateChange = (date: Date) => {
    setCurrentDate(date);

    if (livePreview) {
      setPreviewDate(date);
    }
  };

  return (
    <div className="animation-studio">
      {/* Header */}
      <header className="studio-header">
        <div className="header-content">
          <Link to="/" className="back-link">
            <ArrowLeft size={20} />
            Dashboard
          </Link>
          <div className="header-title">
            <h1>Animation Studio</h1>
            <p>Create time-lapse visualizations of satellite data</p>
          </div>
        </div>
      </header>

      <div className="studio-layout">
        {/* Sidebar - Controls */}
        <aside className="studio-sidebar">
          {/* Region Selection */}
          <section className="control-section">
            <h4>Region</h4>
            <div className="region-select-wrapper">
              <select
                value={selectedRegion?.id || ''}
                onChange={(e) => {
                  const region = regionsData?.regions.find((r) => r.id === e.target.value);
                  setSelectedRegion(region || null);
                }}
                className="region-select"
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
              {regionsLoading && <span className="select-spinner" />}
            </div>
          </section>

          {/* Metric Selection */}
          <section className="control-section">
            <h4>Metric</h4>
            <div className="metric-cards">
              {METRIC_OPTIONS.map((option) => {
                const optionGranularity = option.value === selectedMetric
                  ? granularity
                  : getRecommendedGranularity(option.value, dateRange);
                const optionGranularityLabel = formatGranularityLabel(optionGranularity);

                return (
                <button
                  key={option.value}
                  className={`metric-card ${selectedMetric === option.value ? 'active' : ''}`}
                  onClick={() => setSelectedMetric(option.value)}
                >
                  <span className={`metric-indicator metric-${option.value}`} />
                  <div className="metric-info">
                    <span className="metric-label">
                      {option.label}
                      <span className={`granularity-badge ${optionGranularity}`}>
                        {optionGranularityLabel}
                      </span>
                    </span>
                    <span className="metric-desc">{option.description}</span>
                  </div>
                </button>
                );
              })}
            </div>

            {supportedGranularities.length > 1 && (
              <div className="granularity-toggle">
                <label>Granularity</label>
                <div className="granularity-buttons">
                  {supportedGranularities.map((g) => {
                    const withinLimit =
                      estimateBucketCount(dateRange.start, dateRange.end, g) <= METRICS_MAX_TIMESERIES_POINTS_DEFAULT;
                    const labelText = g.charAt(0).toUpperCase() + g.slice(1);

                    return (
                      <button
                        key={g}
                        className={`granularity-btn ${granularity === g ? 'active' : ''}`}
                        onClick={() => setSelectedGranularity(g)}
                        disabled={!withinLimit}
                        title={
                          withinLimit ? undefined : `Date range too large for ${labelText.toLowerCase()} granularity`
                        }
                      >
                        {labelText}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </section>

          {/* Date Range */}
          <section className="control-section">
            <h4>Date Range</h4>
            <div className="date-inputs">
              <div className="date-field">
                <label>Start</label>
                <input
                  type="date"
                  value={formatDateYYYYMMDD(dateRange.start) ?? dateRange.start.toISOString().split('T')[0]}
                  onChange={(e) =>
                    setDateRange({ ...dateRange, start: parseMetricDate(e.target.value) ?? new Date(e.target.value) })
                  }
                />
              </div>
              <div className="date-field">
                <label>End</label>
                <input
                  type="date"
                  value={formatDateYYYYMMDD(dateRange.end) ?? dateRange.end.toISOString().split('T')[0]}
                  onChange={(e) =>
                    setDateRange({ ...dateRange, end: parseMetricDate(e.target.value) ?? new Date(e.target.value) })
                  }
                />
              </div>
            </div>
          </section>

          {/* Export Settings */}
          <section className="control-section">
            <h4>Export Settings</h4>

            <div className="setting-group">
              <label>Format</label>
              <div className="format-options">
                {FORMAT_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    className={`format-btn ${exportFormat === option.value ? 'active' : ''}`}
                    onClick={() => setExportFormat(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="setting-group">
              <label>Frame Duration</label>
              <div className="slider-with-value">
                <input
                  type="range"
                  min="100"
                  max="2000"
                  step="100"
                  value={frameDuration}
                  onChange={(e) => setFrameDuration(Number(e.target.value))}
                />
                <span className="value">{frameDuration}ms</span>
              </div>
            </div>

            <div className="setting-group">
              <label>Resolution</label>
              <div className="resolution-inputs">
                <input
                  type="number"
                  value={resolution.width}
                  onChange={(e) =>
                    setResolution({ ...resolution, width: Number(e.target.value) })
                  }
                  placeholder="Width"
                />
                <span>x</span>
                <input
                  type="number"
                  value={resolution.height}
                  onChange={(e) =>
                    setResolution({ ...resolution, height: Number(e.target.value) })
                  }
                  placeholder="Height"
                />
              </div>
            </div>
          </section>

          {/* Export Button */}
          <section className="control-section">
            <button
              className="btn btn-primary export-btn"
              onClick={handleExport}
              disabled={!selectedRegion || exportMutation.isPending}
            >
              {exportMutation.isPending ? (
                <>
                  <span className="spinner" />
                  Generating...
                </>
              ) : (
                <>
                  <DownloadSimple size={20} />
                  Export Animation
                </>
              )}
            </button>

            {/* Export Status */}
            {exportStatus && (
              <div className={`export-status status-${exportStatus.status}`}>
                {exportStatus.status === 'pending' && (
                  <p><span className="spinner" /> Queued for processing...</p>
                )}
                {exportStatus.status === 'processing' && (
                  <p><span className="spinner" /> Generating animation...</p>
                )}
                {exportStatus.status === 'completed' && (
                  <>
                    <p className="success">Animation ready!</p>
                    <button className="btn btn-secondary" onClick={handleDownload}>
                      Download {exportFormat.toUpperCase()}
                    </button>
                  </>
                )}
                {exportStatus.status === 'failed' && (
                  <p className="error">Export failed. Please try again.</p>
                )}
              </div>
            )}
          </section>
        </aside>

        {/* Main - Preview */}
        <main className="studio-main">
          <div className="preview-container" ref={previewRef}>
            {selectedRegion ? (
              <>
                <div className="preview-header">
                  <h3>{selectedRegion.name}</h3>
                  <div className="preview-date-stack">
                    <span className="current-date mono">
                      {previewDate && !isNaN(previewDate.getTime())
                        ? `Preview: ${previewDate.toLocaleDateString('en-US', {
                            ...dateLabelOptions,
                          })}`
                        : 'Preview: (not loaded)'}
                    </span>
                    {!livePreview && isPreviewDirty && (
                      <span className="pending-date mono">
                        {currentDate && !isNaN(currentDate.getTime())
                          ? `Selected: ${currentDate.toLocaleDateString('en-US', {
                              ...dateLabelOptions,
                            })}`
                          : 'Selected: Loading...'}
                      </span>
                    )}
                  </div>
                </div>
                <div className="preview-map">
                  <MapView
                    regions={[selectedRegion]}
                    selectedRegion={selectedRegion}
                    selectedMetric={selectedMetric}
                    tileGranularity={granularity}
                    tileDate={previewDate && !isNaN(previewDate.getTime())
                      ? (formatDateYYYYMMDD(previewDate) ?? previewDate.toISOString().split('T')[0])
                      : undefined}
                    overlayEnabled={Boolean(previewDate)}
                    onOverlayLoadingChange={setPreviewOverlayIsLoading}
                    viewLocked={viewLocked}
                  />
                </div>
              </>
            ) : (
              <div className="preview-placeholder">
                <Image size={64} weight="duotone" />
                <p>Select a region to preview</p>
              </div>
            )}
          </div>

          {/* Time Slider */}
          {selectedRegion && availableDates.length > 0 && (
            <div className="timeline-container">
              <div className="timeline-toolbar">
                <div className="timeline-toolbar-left">
                  <label className="live-preview-toggle">
                    <input
                      type="checkbox"
                      checked={livePreview}
                      onChange={(e) => handleToggleLivePreview(e.target.checked)}
                    />
                    Live preview
                  </label>
                  <label className="live-preview-toggle">
                    <input
                      type="checkbox"
                      checked={viewLocked}
                      onChange={(e) => handleToggleViewLock(e.target.checked)}
                    />
                    Lock view
                  </label>
                  {!livePreview && (
                    <button
                      className="btn btn-secondary"
                      onClick={handleApplyPreview}
                      disabled={!isPreviewDirty}
                      title={isPreviewDirty ? 'Update the map preview to the selected date' : 'Preview is up to date'}
                    >
                      Update preview
                    </button>
                  )}
                </div>
              </div>
              <TimeSlider
                dates={availableDates}
                selectedDate={currentDate}
                onDateChange={handleTimelineDateChange}
                isPlaying={isPlaying}
                playbackBlocked={previewOverlayIsLoading}
                onPlayPause={handlePlayPause}
                playbackSpeed={playbackSpeed}
                onSpeedChange={setPlaybackSpeed}
                width={Math.min(800, window.innerWidth - 400)}
              />
            </div>
          )}

          {/* Frame Counter */}
          {selectedRegion && availableDates.length > 0 && (
            <div className="frame-info">
              <span className="frame-count">
                Frame {availableDates.findIndex((d) => d.getTime() === currentDate.getTime()) + 1} of{' '}
                {availableDates.length}
              </span>
              <span className="duration-estimate">
                Est. duration: {((availableDates.length * frameDuration) / 1000).toFixed(1)}s
              </span>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
