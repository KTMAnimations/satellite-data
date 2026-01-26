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
import type { Region, MetricType } from '../types';
import './AnimationStudio.css';

// Parse date string to local Date (avoiding UTC timezone issues)
// Handles: YYYY-MM, YYYY-MM-DD, YYYY-WXX (week format)
function parseYearMonth(dateStr: string): Date {
  // Handle week format (YYYY-WXX)
  if (dateStr.includes('W')) {
    const match = dateStr.match(/^(\d{4})-W(\d{2})$/);
    if (match) {
      const year = parseInt(match[1], 10);
      const week = parseInt(match[2], 10);
      // Calculate the date of the first day of the given ISO week
      // ISO week 1 is the week containing January 4th
      const jan4 = new Date(year, 0, 4);
      const dayOfWeek = jan4.getDay() || 7; // Sunday = 7 in ISO
      const firstMonday = new Date(jan4);
      firstMonday.setDate(jan4.getDate() - dayOfWeek + 1);
      const targetDate = new Date(firstMonday);
      targetDate.setDate(firstMonday.getDate() + (week - 1) * 7);
      return targetDate;
    }
  }

  // Handle YYYY-MM or YYYY-MM-DD format
  const parts = dateStr.split('-').map(Number);
  const year = parts[0];
  const month = parts[1] - 1; // Month is 0-indexed in JavaScript
  const day = parts[2] || 1;
  return new Date(year, month, day);
}

const METRIC_OPTIONS: { value: MetricType; label: string; description: string; granularity: string }[] = [
  // Original metrics
  { value: 'nightlights', label: 'Nighttime Lights', description: 'Urban activity proxy (daily available)', granularity: 'Daily' },
  { value: 'ndvi', label: 'NDVI', description: 'Vegetation index showing greenness', granularity: 'Weekly' },
  { value: 'urban_density', label: 'Urban Density', description: 'Built-up area estimation', granularity: 'Monthly' },
  { value: 'parking', label: 'Parking Occupancy', description: 'Parking lot fill levels', granularity: 'Weekly' },
  // Phase 1: Core datasets
  { value: 'land_cover', label: 'Land Cover', description: 'Dynamic World built-up probability', granularity: 'Monthly' },
  { value: 'surface_water', label: 'Surface Water', description: 'JRC water extent mapping', granularity: 'Monthly' },
  { value: 'active_fire', label: 'Active Fire', description: 'VIIRS 375m fire detections (daily)', granularity: 'Daily' },
  // Phase 2: Air quality & weather
  { value: 'no2', label: 'NO₂', description: 'Tropospheric nitrogen dioxide', granularity: 'Monthly' },
  { value: 'temperature', label: 'Temperature', description: 'ERA5-Land 2m air temperature', granularity: 'Monthly' },
  { value: 'precipitation', label: 'Precipitation', description: 'ERA5-Land total precipitation', granularity: 'Monthly' },
  { value: 'aerosol', label: 'Aerosol', description: 'UV Aerosol Index (smoke/dust)', granularity: 'Monthly' },
  // Phase 3: Agriculture
  { value: 'cropland', label: 'Cropland', description: 'USDA crop type classification', granularity: 'Yearly' },
  { value: 'evapotranspiration', label: 'Evapotranspiration', description: 'OpenET water use', granularity: 'Monthly' },
  { value: 'soil_moisture', label: 'Soil Moisture', description: 'SMAP root-zone moisture', granularity: 'Monthly' },
  // Phase 4: Historical & specialized
  { value: 'impervious', label: 'Impervious Surface', description: 'GAIA urban expansion', granularity: 'Yearly' },
  { value: 'fire_historical', label: 'Historical Fire', description: 'MODIS FIRMS archive (2000+)', granularity: 'Monthly' },
  { value: 'canopy_height', label: 'Canopy Height', description: 'GEDI forest structure', granularity: 'Static' },
];

const FORMAT_OPTIONS = [
  { value: 'gif', label: 'GIF', description: 'Animated image, widely compatible' },
  { value: 'webm', label: 'WebM', description: 'Modern video format, smaller size' },
];

// Finest available granularity per metric (based on data source limitations)
// nightlights now supports daily via NASA Black Marble VNP46A2
const METRIC_GRANULARITY: Record<MetricType, 'daily' | 'weekly' | 'monthly'> = {
  // Original metrics
  ndvi: 'weekly',           // Sentinel-2: 5-day revisit
  parking: 'weekly',        // Sentinel-2: 5-day revisit
  nightlights: 'daily',     // VIIRS: daily via NASA Black Marble, monthly via NOAA composites
  urban_density: 'monthly', // GHSL: static epochs
  // Phase 1: Core datasets
  land_cover: 'monthly',    // Dynamic World: near real-time but monthly composites
  surface_water: 'monthly', // JRC: monthly from 1984-2021
  active_fire: 'daily',     // VIIRS 375m: near real-time daily
  // Phase 2: Air quality & weather
  no2: 'monthly',           // S5P: daily available but monthly composites for visualization
  temperature: 'monthly',   // ERA5-Land: hourly but monthly averages
  precipitation: 'monthly', // ERA5-Land: hourly but monthly totals
  aerosol: 'monthly',       // S5P: daily but monthly composites
  // Phase 3: Agriculture
  cropland: 'monthly',      // USDA CDL: annual (use monthly for UI)
  evapotranspiration: 'monthly', // OpenET: monthly
  soil_moisture: 'monthly', // SMAP: 3-day revisit, monthly composites
  // Phase 4: Historical & specialized
  impervious: 'monthly',    // GAIA: annual snapshots 1985-2018
  fire_historical: 'monthly', // MODIS FIRMS: daily but monthly composites
  canopy_height: 'monthly', // GEDI: static dataset
};

export function AnimationStudio() {
  const [selectedRegion, setSelectedRegion] = useState<Region | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<MetricType>('nightlights');
  const [dateRange, setDateRange] = useState({
    start: new Date(2024, 0, 1),   // Jan 1, 2024 - matches available tile data
    end: new Date(2024, 0, 31),    // Jan 31, 2024 - matches available tile data
  });
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentDate, setCurrentDate] = useState<Date>(dateRange.start);
  const [exportFormat, setExportFormat] = useState<'gif' | 'webm'>('gif');
  const [frameDuration, setFrameDuration] = useState(500);
  const [resolution, setResolution] = useState({ width: 800, height: 600 });
  const [exportId, setExportId] = useState<string | null>(null);

  const previewRef = useRef<HTMLDivElement>(null);

  // Fetch regions
  const { data: regionsData } = useQuery({
    queryKey: ['regions', 'predefined'],
    queryFn: () => api.listRegions({ type: 'predefined', page_size: 50 }),
  });

  // Fetch metrics for date generation - use finest granularity per metric
  const granularity = METRIC_GRANULARITY[selectedMetric];
  const { data: metrics } = useQuery({
    queryKey: ['metrics', selectedRegion?.id, selectedMetric, granularity, dateRange],
    queryFn: () =>
      api.getMetrics(selectedRegion!.id, {
        start_date: dateRange.start.toISOString().split('T')[0],
        end_date: dateRange.end.toISOString().split('T')[0],
        granularity,
      }),
    enabled: !!selectedRegion,
  });

  // Generate date array from metrics - memoized to prevent infinite loops
  // Backend returns YYYY-MM format for monthly data
  const availableDates = useMemo(() => {
    const data = metrics?.metrics[selectedMetric]?.data;
    if (!data) return [];
    return data.map((d) => parseYearMonth(d.date));
  }, [metrics, selectedMetric]);

  // Export mutation
  const exportMutation = useMutation({
    mutationFn: () =>
      api.exportAnimation({
        region_id: selectedRegion!.id,
        metric: selectedMetric,
        format: exportFormat,
        start_date: dateRange.start.toISOString().split('T')[0],
        end_date: dateRange.end.toISOString().split('T')[0],
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
    queryFn: () => api.getExportStatus(exportId!),
    enabled: !!exportId && exportMutation.isSuccess,
    refetchInterval: (query) =>
      query.state.data?.status === 'completed' || query.state.data?.status === 'failed'
        ? false
        : 2000,
  });

  // Playback loop
  useEffect(() => {
    if (!isPlaying || availableDates.length === 0) return;

    const interval = setInterval(() => {
      setCurrentDate((prev) => {
        const currentIndex = availableDates.findIndex(
          (d) => d.getTime() === prev.getTime()
        );
        const nextIndex = (currentIndex + 1) % availableDates.length;
        return availableDates[nextIndex];
      });
    }, 1000 / playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, availableDates, playbackSpeed]);

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
    } else {
      // Reset to date range start when no dates available (e.g., during metric switch)
      setCurrentDate(dateRange.start);
    }
  }, [availableDatesKey, dateRange.start, selectedMetric]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleExport = () => {
    if (!selectedRegion) return;
    exportMutation.mutate();
  };

  const handleDownload = () => {
    if (exportStatus?.download_url) {
      window.open(api.getExportDownloadUrl(exportId!), '_blank');
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
            <select
              value={selectedRegion?.id || ''}
              onChange={(e) => {
                const region = regionsData?.regions.find((r) => r.id === e.target.value);
                setSelectedRegion(region || null);
              }}
              className="region-select"
            >
              <option value="">Select a region...</option>
              {regionsData?.regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </section>

          {/* Metric Selection */}
          <section className="control-section">
            <h4>Metric</h4>
            <div className="metric-cards">
              {METRIC_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  className={`metric-card ${selectedMetric === option.value ? 'active' : ''}`}
                  onClick={() => setSelectedMetric(option.value)}
                >
                  <span className={`metric-indicator metric-${option.value}`} />
                  <div className="metric-info">
                    <span className="metric-label">
                      {option.label}
                      <span className={`granularity-badge ${option.granularity.toLowerCase()}`}>
                        {option.granularity}
                      </span>
                    </span>
                    <span className="metric-desc">{option.description}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          {/* Date Range */}
          <section className="control-section">
            <h4>Date Range</h4>
            <div className="date-inputs">
              <div className="date-field">
                <label>Start</label>
                <input
                  type="date"
                  value={dateRange.start.toISOString().split('T')[0]}
                  onChange={(e) =>
                    setDateRange({ ...dateRange, start: new Date(e.target.value) })
                  }
                />
              </div>
              <div className="date-field">
                <label>End</label>
                <input
                  type="date"
                  value={dateRange.end.toISOString().split('T')[0]}
                  onChange={(e) =>
                    setDateRange({ ...dateRange, end: new Date(e.target.value) })
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
                    onClick={() => setExportFormat(option.value as 'gif' | 'webm')}
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
                  <span className="current-date mono">
                    {currentDate && !isNaN(currentDate.getTime())
                      ? currentDate.toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'long',
                        })
                      : 'Loading...'}
                  </span>
                </div>
                <div className="preview-map">
                  <MapView
                    regions={[selectedRegion]}
                    selectedRegion={selectedRegion}
                    selectedMetric={selectedMetric}
                    tileDate={currentDate && !isNaN(currentDate.getTime())
                      ? currentDate.toISOString().split('T')[0]
                      : undefined}
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
              <TimeSlider
                dates={availableDates}
                selectedDate={currentDate}
                onDateChange={setCurrentDate}
                isPlaying={isPlaying}
                onPlayPause={() => setIsPlaying(!isPlaying)}
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
