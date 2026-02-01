import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
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
import api from '../services/api';
import { useStore } from '../store';
import { formatApiError } from '../utils/errors';
import type { MetricType } from '../types';
import './ExportCenter.css';

const METRIC_OPTIONS: { value: MetricType; label: string }[] = [
  { value: 'nightlights', label: 'Nighttime Lights' },
  { value: 'ndvi', label: 'NDVI (Vegetation)' },
  { value: 'urban_density', label: 'Urban Density' },
  { value: 'parking', label: 'Parking Occupancy' },
  { value: 'land_cover', label: 'Land Cover' },
  { value: 'surface_water', label: 'Surface Water' },
  { value: 'no2', label: 'NO2 Air Quality' },
  { value: 'temperature', label: 'Temperature' },
  { value: 'precipitation', label: 'Precipitation' },
  { value: 'aerosol', label: 'Aerosol Index' },
  { value: 'cropland', label: 'Cropland' },
  { value: 'evapotranspiration', label: 'Evapotranspiration' },
  { value: 'soil_moisture', label: 'Soil Moisture' },
  { value: 'impervious', label: 'Impervious Surface' },
  { value: 'canopy_height', label: 'Canopy Height' },
];

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
  const exportQueue = useStore((state) => state.exportQueue);
  const addExportToQueue = useStore((state) => state.addExportToQueue);
  const setExportQueue = useStore((state) => state.setExportQueue);

  const { data: regionsData, isLoading: regionsLoading, isError: regionsIsError, error: regionsError } = useQuery({
    queryKey: ['regions', { page_size: 100 }],
    queryFn: ({ signal }) => api.listRegions({ page_size: 100 }, { signal }),
  });

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
        start_date: startDate,
        end_date: endDate,
        frame_duration_ms: 500,
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

  const handleExport = () => {
    if (!selectedRegionId) {
      alert('Please select a region');
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
              <button
                className={`format-btn ${exportFormat === 'animation' ? 'active' : ''}`}
                onClick={() => setExportFormat('animation')}
              >
                <FilmStrip size={24} weight="duotone" className="format-icon" />
                <span>Animation</span>
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
              : `Generate ${exportFormat.toUpperCase()}`}
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
                        <span>Created: {new Date(exp.created_at).toLocaleString()}</span>
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
