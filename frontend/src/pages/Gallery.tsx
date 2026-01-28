import { useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { Icon } from '@phosphor-icons/react';
import {
  Bird,
  Virus,
  Buildings,
  GraduationCap,
  AirplaneTilt,
} from '@phosphor-icons/react';
import './Gallery.css';
import api from '../services/api';
import { formatApiError } from '../utils/errors';

const PRESET_ICONS: Record<string, Icon> = {
  'snowbird': Bird,
  'covid': Virus,
  'urban-growth': Buildings,
  'college-towns': GraduationCap,
  'tourism': AirplaneTilt,
};

export function Gallery() {
  const [searchParams] = useSearchParams();
  const highlightedPreset = searchParams.get('preset');
  const presetRefs = useRef<Record<string, HTMLElement | null>>({});

  const { data: presetsData, isLoading, isError, error } = useQuery({
    queryKey: ['presets'],
    queryFn: () => api.listPresets(),
  });
  const presets = presetsData?.presets ?? [];

  // Scroll to highlighted preset when navigating from Dashboard
  useEffect(() => {
    if (highlightedPreset && presetRefs.current[highlightedPreset]) {
      presetRefs.current[highlightedPreset]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [highlightedPreset]);

  return (
    <div className="gallery">
      <header className="gallery-header">
        <h1>Gallery</h1>
        <p>
          Explore curated presets. Click any preset to apply its regions, metrics, and date
          range in the Region Explorer.
        </p>
      </header>

      <div className="presets-grid">
        {isLoading ? (
          <div className="loading">Loading presets...</div>
        ) : isError ? (
          <div className="loading">Error loading presets: {formatApiError(error)}</div>
        ) : (
          presets.map((preset) => (
          <article
            key={preset.id}
            ref={(el) => (presetRefs.current[preset.id] = el)}
            className={`preset-card ${highlightedPreset === preset.id ? 'highlighted' : ''}`}
          >
            <div className="preset-image">
              <div className="preset-image-placeholder">
                {(() => {
                  const Icon = PRESET_ICONS[preset.id];
                  return Icon ? <Icon size={48} weight="duotone" /> : null;
                })()}
              </div>
            </div>

            <div className="preset-content">
              <h2>{preset.name}</h2>
              <p className="preset-description">{preset.description}</p>

              <div className="preset-details">
                <div className="detail-row">
                  <span className="detail-label">Regions:</span>
                  <span className="detail-value">{preset.regions.map((r) => r.name).join(', ')}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Metrics:</span>
                  <span className="detail-value">
                    {preset.metrics.map((m) => m.replace('_', ' ')).join(', ')}
                  </span>
                </div>
                {preset.date_range && (
                  <div className="detail-row">
                    <span className="detail-label">Date Range:</span>
                    <span className="detail-value">
                      {preset.date_range.start_date} to {preset.date_range.end_date}
                    </span>
                  </div>
                )}
                {preset.compare && (
                  <div className="detail-row">
                    <span className="detail-label">Comparison:</span>
                    <span className="detail-value">
                      {(preset.compare.period_a.label ?? 'Period A')} vs {(preset.compare.period_b.label ?? 'Period B')}
                    </span>
                  </div>
                )}
              </div>

              <Link to={`/regions?preset=${preset.id}`} className="btn btn-primary">
                Explore Analysis
              </Link>
            </div>
          </article>
          ))
        )}
      </div>

      {/* Methodology Note */}
      <section className="methodology-section">
        <h2>Methodology</h2>
        <p>
          These analyses use proxy metrics derived from free satellite data. At 10m resolution
          (Sentinel-2), individual vehicles cannot be detected. Instead, we measure:
        </p>
        <ul>
          <li>
            <strong>Nighttime Lights (VIIRS):</strong> Intensity of artificial lighting as a
            proxy for population and economic activity
          </li>
          <li>
            <strong>NDVI:</strong> Vegetation density to track urban sprawl and seasonal
            changes
          </li>
          <li>
            <strong>Urban Density:</strong> Built-up area estimation using spectral indices
          </li>
          <li>
            <strong>Parking Occupancy:</strong> Aggregate patterns in large parking lots
          </li>
        </ul>
        <p className="disclaimer">
          <strong>Note:</strong> All metrics are correlational proxies, not direct
          measurements. Results should be interpreted as relative trends rather than absolute
          values.
        </p>
      </section>
    </div>
  );
}
