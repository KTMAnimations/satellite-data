import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import './Gallery.css';

/* ─────────────────────────────────────────────────────────────────────────
   Static preset data & themes — no backend dependency.
   ───────────────────────────────────────────────────────────────────────── */

interface GalleryPreset {
  id: string;
  name: string;
  description: string;
  regions: string[];
  metrics: string[];
  period: string | null;
  compare: string | null;
}

interface PresetTheme {
  gradient: string;
  accent: string;
  label: string;
  number: string;
}

const PRESETS: GalleryPreset[] = [
  {
    id: 'snowbird',
    name: 'Snowbird Migration Pattern',
    description:
      'Track how winter populations swell in Sun Belt cities like Phoenix, Miami, and Tampa by comparing seasonal proxy metrics.',
    regions: ['Phoenix, AZ', 'Miami, FL', 'Tampa, FL', 'Tucson, AZ'],
    metrics: ['Nightlights', 'Parking'],
    period: '2024-01-01 — 2025-12-31',
    compare: 'Winter vs Summer',
  },
  {
    id: 'covid',
    name: 'COVID-19 Impact Analysis',
    description:
      'Examine how urban activity collapsed in 2020 and recovered through 2022. This preset compares major metropolitan areas across the pandemic timeline.',
    regions: ['New York, NY', 'San Francisco, CA', 'Las Vegas, NV'],
    metrics: ['Nightlights', 'Parking', 'Urban Density'],
    period: '2019-01-01 — 2022-12-31',
    compare: '2019 Baseline vs 2020 COVID',
  },
  {
    id: 'urban-growth',
    name: 'Urban Growth: Phoenix (2015-2025)',
    description:
      'Track long-term urban expansion using satellite-derived proxy metrics over the Sentinel-2 era.',
    regions: ['Phoenix, AZ'],
    metrics: ['Urban Density', 'NDVI', 'Impervious'],
    period: '2015-01-01 — 2025-12-31',
    compare: null,
  },
  {
    id: 'college-towns',
    name: 'College Town Seasonality',
    description:
      'University towns show distinct seasonal patterns driven by academic calendars. Compare activity during the school year (Sep-May) versus summer break.',
    regions: ['Austin, TX', 'Ann Arbor, MI', 'Boulder, CO'],
    metrics: ['Nightlights', 'Parking'],
    period: '2024-09-01 — 2025-08-31',
    compare: 'Academic Year vs Summer Break',
  },
  {
    id: 'tourism',
    name: 'Tourist Destination Patterns',
    description:
      'Tourism-driven economies show predictable seasonal activity fluctuations. Analyze peak vs off-peak patterns in major tourist destinations.',
    regions: ['Las Vegas, NV', 'Orlando, FL'],
    metrics: ['Nightlights', 'Parking'],
    period: '2024-01-01 — 2024-12-31',
    compare: 'Peak Season (Summer) vs Off-Peak (Winter)',
  },
];

const THEMES: Record<string, PresetTheme> = {
  snowbird: {
    gradient: 'linear-gradient(135deg, #0D9488 0%, #5EEAD4 40%, #F0FDFA 100%)',
    accent: '#0D9488',
    label: 'SEASONAL MIGRATION',
    number: '001',
  },
  covid: {
    gradient: 'linear-gradient(135deg, #7C3AED 0%, #A78BFA 40%, #EDE9FE 100%)',
    accent: '#7C3AED',
    label: 'TEMPORAL IMPACT',
    number: '002',
  },
  'urban-growth': {
    gradient: 'linear-gradient(135deg, #D97706 0%, #FCD34D 40%, #FFFBEB 100%)',
    accent: '#D97706',
    label: 'URBAN EXPANSION',
    number: '003',
  },
  'college-towns': {
    gradient: 'linear-gradient(135deg, #059669 0%, #6EE7B7 40%, #ECFDF5 100%)',
    accent: '#059669',
    label: 'ACADEMIC CYCLES',
    number: '004',
  },
  tourism: {
    gradient: 'linear-gradient(135deg, #DC2626 0%, #FCA5A5 40%, #FEF2F2 100%)',
    accent: '#DC2626',
    label: 'TOURISM PATTERNS',
    number: '005',
  },
};

const DEFAULT_THEME: PresetTheme = {
  gradient: 'linear-gradient(135deg, #78716C 0%, #D6D3D1 40%, #F5F5F4 100%)',
  accent: '#78716C',
  label: 'ANALYSIS',
  number: '000',
};

/* ─────────────────────────────────────────────────────────────────────────
   Gallery Card
   ───────────────────────────────────────────────────────────────────────── */
function GalleryCard({
  preset,
  theme,
  highlighted,
  index,
  innerRef,
}: {
  preset: GalleryPreset;
  theme: PresetTheme;
  highlighted: boolean;
  index: number;
  innerRef: (el: HTMLElement | null) => void;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <article
      ref={innerRef}
      className={`gallery-card ${highlighted ? 'gallery-card--highlighted' : ''}`}
      style={{
        '--card-accent': theme.accent,
        '--card-gradient': theme.gradient,
        animationDelay: `${index * 0.08}s`,
      } as React.CSSProperties}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="gallery-card__visual">
        <div className="gallery-card__gradient" />
        <div className="gallery-card__number">{theme.number}</div>
        <div className={`gallery-card__label ${hovered ? 'gallery-card__label--visible' : ''}`}>
          {theme.label}
        </div>
      </div>

      <div className="gallery-card__body">
        <h2 className="gallery-card__title">{preset.name}</h2>
        <p className="gallery-card__description">{preset.description}</p>

        <div className="gallery-card__meta">
          <div className="gallery-card__meta-group">
            <span className="gallery-card__meta-label">Regions</span>
            <span className="gallery-card__meta-value">{preset.regions.join(' / ')}</span>
          </div>
          <div className="gallery-card__meta-group">
            <span className="gallery-card__meta-label">Metrics</span>
            <span className="gallery-card__meta-value">{preset.metrics.join(' / ')}</span>
          </div>
          {preset.period && (
            <div className="gallery-card__meta-group">
              <span className="gallery-card__meta-label">Period</span>
              <span className="gallery-card__meta-value">{preset.period}</span>
            </div>
          )}
          {preset.compare && (
            <div className="gallery-card__meta-group">
              <span className="gallery-card__meta-label">Comparing</span>
              <span className="gallery-card__meta-value">{preset.compare}</span>
            </div>
          )}
        </div>

        <Link to={`/regions?preset=${preset.id}`} className="gallery-card__link">
          View Analysis
        </Link>
      </div>
    </article>
  );
}

/* ─────────────────────────────────────────────────────────────────────────
   Gallery Page
   ───────────────────────────────────────────────────────────────────────── */
export function Gallery() {
  const [searchParams] = useSearchParams();
  const highlightedPreset = searchParams.get('preset');
  const presetRefs = useRef<Record<string, HTMLElement | null>>({});

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
        <div className="gallery-header__label">Curated Analyses</div>
        <h1 className="gallery-header__title">Gallery</h1>
        <p className="gallery-header__subtitle">
          Satellite-derived insights across migration, urbanization, and seasonal change.
          Select any study to explore its data.
        </p>
      </header>

      <div className="gallery-divider" />

      <div className="gallery-grid">
        {PRESETS.map((preset, i) => {
          const theme = THEMES[preset.id] ?? DEFAULT_THEME;
          return (
            <GalleryCard
              key={preset.id}
              preset={preset}
              theme={theme}
              highlighted={highlightedPreset === preset.id}
              index={i}
              innerRef={(el) => {
                presetRefs.current[preset.id] = el;
              }}
            />
          );
        })}
      </div>

      <footer className="gallery-footer">
        <div className="gallery-divider" />
        <div className="gallery-footer__content">
          <h6 className="gallery-footer__heading">About These Analyses</h6>
          <p>
            All studies use proxy metrics derived from free satellite imagery.
            At 10m resolution (Sentinel-2), individual vehicles cannot be detected.
            Metrics include nighttime light intensity (VIIRS), vegetation density (NDVI),
            built-up area estimation, and aggregate parking lot patterns.
            Results are correlational proxies — interpret as relative trends, not absolute values.
          </p>
        </div>
      </footer>
    </div>
  );
}
