import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import {
  Bird,
  Virus,
  Buildings,
  GraduationCap,
  Airplane,
  MapPin,
  Calendar,
  ChartLine,
  Export,
  Planet,
  Database,
} from '@phosphor-icons/react';
import { MapView } from '../components/Map/MapContainer';
import api from '../services/api';
import './Dashboard.css';

const PRESET_ICONS = {
  'snowbird': Bird,
  'covid': Virus,
  'urban-growth': Buildings,
  'college-towns': GraduationCap,
  'tourism': Airplane,
} as const;

const FEATURED_PRESET_ORDER = ['snowbird', 'covid', 'urban-growth', 'college-towns', 'tourism'] as const;

export function Dashboard() {
  const navigate = useNavigate();
  const { data: regionsData } = useQuery({
    queryKey: ['regions', { type: 'predefined', page_size: 100 }],
    queryFn: () => api.listRegions({ type: 'predefined', page_size: 100 }),
  });

  const { data: presetsData } = useQuery({
    queryKey: ['presets'],
    queryFn: () => api.listPresets(),
  });

  const presets = presetsData?.presets ?? [];
  const presetsById = new Map(presets.map((p) => [p.id, p] as const));
  const featuredPresets = FEATURED_PRESET_ORDER
    .map((id) => presetsById.get(id))
    .filter((p): p is NonNullable<typeof p> => Boolean(p));

  const stats = [
    { label: 'Predefined Regions', value: regionsData?.total || 0 },
    { label: 'Data Coverage', value: '2015-Present' },
    { label: 'Metrics Available', value: 17 },
    { label: 'Resolution', value: '10m (Sentinel-2)' },
  ];

  const quickStartSteps = [
    { number: 1, title: 'Select a Region', description: 'Choose from predefined cities or draw a custom polygon on the map.', icon: MapPin },
    { number: 2, title: 'Choose Time Period', description: 'Select date ranges or use presets like "Winter vs Summer" for seasonal comparisons.', icon: Calendar },
    { number: 3, title: 'Analyze Metrics', description: 'View nighttime lights, vegetation indices, and urban density patterns over time.', icon: ChartLine },
    { number: 4, title: 'Export Results', description: 'Generate PDF reports, download CSV data, or create time-lapse animations.', icon: Export },
  ];

  return (
    <div className="dashboard">
      {/* Hero Section */}
      <section className="dashboard-hero">
        <div className="hero-content">
          <div className="hero-icon">
            <Planet size={48} weight="duotone" />
          </div>
          <h1>Satellite Migration Analysis</h1>
          <p>
            Analyze seasonal migration patterns, urban growth, and activity changes
            using satellite-derived proxy metrics from free data sources.
          </p>
          <div className="hero-actions">
            <Link to="/regions" className="btn btn-primary">
              Explore Regions
            </Link>
            <Link to="/gallery" className="btn btn-outline">
              View Examples
            </Link>
          </div>
        </div>
        <div className="hero-map">
          <MapView
            regions={regionsData?.regions || []}
            onRegionSelect={(region) => {
              navigate(`/regions/${region.id}`);
            }}
          />
        </div>
      </section>

      {/* Stats */}
      <section className="dashboard-stats">
        {stats.map((stat) => (
          <div key={stat.label} className="stat-card instrument-panel">
            <span className="bracket-bl" />
            <span className="bracket-br" />
            <div className="stat-value mono">{stat.value}</div>
            <div className="stat-label">{stat.label}</div>
          </div>
        ))}
      </section>

      {/* Featured Analyses */}
      <section className="dashboard-section">
        <h2>Featured Analyses</h2>
        <div className="featured-grid">
          {featuredPresets.map((preset) => {
            const Icon = PRESET_ICONS[preset.id as keyof typeof PRESET_ICONS] ?? Planet;
            return (
              <Link
                key={preset.id}
                to={`/gallery?preset=${preset.id}`}
                className="featured-card instrument-panel"
              >
                <span className="bracket-bl" />
                <span className="bracket-br" />
                <div className="featured-header">
                  <div className="featured-icon">
                    <Icon size={24} weight="duotone" />
                  </div>
                  {preset.category && <span className="featured-category">{preset.category}</span>}
                </div>
                <h3>{preset.name}</h3>
                <p>{preset.description}</p>
                <div className="featured-regions">
                  {preset.regions.slice(0, 3).map((region) => (
                    <span key={region.name} className="region-tag">
                      {region.name}
                    </span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Quick Start */}
      <section className="dashboard-section">
        <h2>Quick Start</h2>
        <div className="quickstart-grid">
          {quickStartSteps.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.number} className="quickstart-card instrument-panel">
                <span className="bracket-bl" />
                <span className="bracket-br" />
                <div className="quickstart-header">
                  <div className="quickstart-number mono">{step.number}</div>
                  <div className="quickstart-icon">
                    <Icon size={20} weight="duotone" />
                  </div>
                </div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Data Sources */}
      <section className="dashboard-section">
        <h2>Data Sources</h2>
        <div className="sources-grid">
          <div className="source-card">
            <div className="source-icon">
              <Planet size={20} weight="duotone" />
            </div>
            <div className="source-content">
              <h4>Sentinel-2</h4>
              <p>10m optical imagery for NDVI, urban density</p>
              <span className="source-badge">Primary</span>
            </div>
          </div>
          <div className="source-card">
            <div className="source-icon">
              <Planet size={20} weight="duotone" />
            </div>
            <div className="source-content">
              <h4>VIIRS</h4>
              <p>375m nighttime lights for activity proxy</p>
              <span className="source-badge">Primary</span>
            </div>
          </div>
          <div className="source-card">
            <div className="source-icon">
              <Buildings size={20} weight="duotone" />
            </div>
            <div className="source-content">
              <h4>GHSL</h4>
              <p>Global Human Settlement Layer for built-up areas</p>
              <span className="source-badge badge-secondary">Supplementary</span>
            </div>
          </div>
          <div className="source-card">
            <div className="source-icon">
              <Database size={20} weight="duotone" />
            </div>
            <div className="source-content">
              <h4>OpenStreetMap</h4>
              <p>Road networks and POIs for context</p>
              <span className="source-badge badge-secondary">Supplementary</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
