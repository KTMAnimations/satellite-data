import { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  DownloadSimple,
  Image,
  Spinner,
  CheckCircle,
  WarningCircle,
} from '@phosphor-icons/react';
import { MapView } from '../components/Map/MapContainer';
import { TimeSlider } from '../components/Charts/TimeSlider';
import api from '../services/api';
import type { Region, MetricType } from '../types';
import './AnimationStudio.css';

const METRIC_OPTIONS: { value: MetricType; label: string; description: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights', description: 'Urban activity and population density proxy' },
  { value: 'ndvi', label: 'NDVI', description: 'Vegetation index showing greenness' },
  { value: 'urban_density', label: 'Urban Density', description: 'Built-up area estimation' },
  { value: 'parking', label: 'Parking Occupancy', description: 'Parking lot fill levels' },
];

const FORMAT_OPTIONS = [
  { value: 'gif', label: 'GIF', description: 'Animated image, widely compatible' },
  { value: 'webm', label: 'WebM', description: 'Modern video format, smaller size' },
];

export function AnimationStudio() {
  const [selectedRegion, setSelectedRegion] = useState<Region | null>(null);
  const [selectedMetric, setSelectedMetric] = useState<MetricType>('nightlights');
  const [dateRange, setDateRange] = useState({
    start: new Date(2023, 0, 1),  // Jan 1, 2023 - matches available data
    end: new Date(2024, 11, 31),  // Dec 31, 2024 - matches available data
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

  // Fetch metrics for date generation
  const { data: metrics } = useQuery({
    queryKey: ['metrics', selectedRegion?.id, dateRange],
    queryFn: () =>
      api.getMetrics(selectedRegion!.id, {
        start_date: dateRange.start.toISOString().split('T')[0],
        end_date: dateRange.end.toISOString().split('T')[0],
        granularity: 'monthly',
      }),
    enabled: !!selectedRegion,
  });

  // Generate date array from metrics
  const availableDates = metrics?.metrics[selectedMetric]?.data.map(
    (d) => new Date(d.date)
  ) || [];

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

  // Initialize current date when dates change
  useEffect(() => {
    if (availableDates.length > 0) {
      setCurrentDate(availableDates[0]);
    }
  }, [availableDates.length]);

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
                    <span className="metric-label">{option.label}</span>
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
                    {currentDate.toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                    })}
                  </span>
                </div>
                <div className="preview-map">
                  <MapView
                    regions={[selectedRegion]}
                    selectedRegion={selectedRegion}
                    selectedMetric={selectedMetric}
                    tileDate={currentDate.toISOString().split('T')[0]}
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
