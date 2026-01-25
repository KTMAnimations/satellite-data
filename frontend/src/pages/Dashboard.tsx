import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { MapView } from '../components/Map/MapContainer';
import api from '../services/api';
import './Dashboard.css';

export function Dashboard() {
  const { data: regionsData, isLoading } = useQuery({
    queryKey: ['regions', { type: 'predefined', page_size: 100 }],
    queryFn: () => api.listRegions({ type: 'predefined', page_size: 100 }),
  });

  const featuredAnalyses = [
    {
      id: 'snowbird',
      title: 'Snowbird Migration Pattern',
      description: 'Track winter population shifts to Sun Belt cities',
      regions: ['Phoenix, AZ', 'Miami, FL', 'Tampa, FL'],
      icon: '🦅',
    },
    {
      id: 'covid',
      title: 'COVID-19 Impact Analysis',
      description: 'Activity collapse and recovery patterns 2020-2022',
      regions: ['New York, NY', 'San Francisco, CA', 'Las Vegas, NV'],
      icon: '🦠',
    },
    {
      id: 'urban-growth',
      title: 'Urban Growth: Phoenix 2015-2024',
      description: 'Tracking one of Americas fastest-growing cities',
      regions: ['Phoenix Metro'],
      icon: '🏗️',
    },
    {
      id: 'college-towns',
      title: 'College Town Seasonality',
      description: 'University impact on city activity patterns',
      regions: ['Austin, TX', 'Ann Arbor, MI', 'Boulder, CO'],
      icon: '🎓',
    },
  ];

  const stats = [
    { label: 'Predefined Regions', value: regionsData?.total || 0 },
    { label: 'Data Coverage', value: '2015-Present' },
    { label: 'Metrics Available', value: 4 },
    { label: 'Resolution', value: '10m (Sentinel-2)' },
  ];

  return (
    <div className="dashboard">
      {/* Hero Section */}
      <section className="dashboard-hero">
        <div className="hero-content">
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
              window.location.href = `/regions/${region.id}`;
            }}
          />
        </div>
      </section>

      {/* Stats */}
      <section className="dashboard-stats">
        {stats.map((stat) => (
          <div key={stat.label} className="stat-card">
            <div className="stat-value">{stat.value}</div>
            <div className="stat-label">{stat.label}</div>
          </div>
        ))}
      </section>

      {/* Featured Analyses */}
      <section className="dashboard-section">
        <h2>Featured Analyses</h2>
        <div className="featured-grid">
          {featuredAnalyses.map((analysis) => (
            <Link
              key={analysis.id}
              to={`/gallery?preset=${analysis.id}`}
              className="featured-card"
            >
              <div className="featured-icon">{analysis.icon}</div>
              <h3>{analysis.title}</h3>
              <p>{analysis.description}</p>
              <div className="featured-regions">
                {analysis.regions.map((region) => (
                  <span key={region} className="region-tag">
                    {region}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Quick Start */}
      <section className="dashboard-section">
        <h2>Quick Start</h2>
        <div className="quickstart-grid">
          <div className="quickstart-card">
            <div className="quickstart-number">1</div>
            <h3>Select a Region</h3>
            <p>
              Choose from predefined cities or draw a custom polygon on the map.
            </p>
          </div>
          <div className="quickstart-card">
            <div className="quickstart-number">2</div>
            <h3>Choose Time Period</h3>
            <p>
              Select date ranges or use presets like "Winter vs Summer" for
              seasonal comparisons.
            </p>
          </div>
          <div className="quickstart-card">
            <div className="quickstart-number">3</div>
            <h3>Analyze Metrics</h3>
            <p>
              View nighttime lights, vegetation indices, and urban density
              patterns over time.
            </p>
          </div>
          <div className="quickstart-card">
            <div className="quickstart-number">4</div>
            <h3>Export Results</h3>
            <p>
              Generate PDF reports, download CSV data, or create time-lapse
              animations.
            </p>
          </div>
        </div>
      </section>

      {/* Data Sources */}
      <section className="dashboard-section">
        <h2>Data Sources</h2>
        <div className="sources-grid">
          <div className="source-card">
            <h4>Sentinel-2</h4>
            <p>10m optical imagery for NDVI, urban density</p>
            <span className="source-badge">Primary</span>
          </div>
          <div className="source-card">
            <h4>VIIRS</h4>
            <p>375m nighttime lights for activity proxy</p>
            <span className="source-badge">Primary</span>
          </div>
          <div className="source-card">
            <h4>GHSL</h4>
            <p>Global Human Settlement Layer for built-up areas</p>
            <span className="source-badge">Supplementary</span>
          </div>
          <div className="source-card">
            <h4>OpenStreetMap</h4>
            <p>Road networks and POIs for context</p>
            <span className="source-badge">Supplementary</span>
          </div>
        </div>
      </section>
    </div>
  );
}
