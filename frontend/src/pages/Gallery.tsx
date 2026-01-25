import { Link } from 'react-router-dom';
import './Gallery.css';

const PRESETS = [
  {
    id: 'snowbird',
    title: 'Snowbird Migration Pattern',
    description:
      'Track how winter populations swell in Sun Belt cities like Phoenix, Miami, and Tampa. This analysis compares nighttime light intensity between December-February and June-August.',
    regions: ['Phoenix, AZ', 'Miami, FL', 'Tampa, FL', 'Tucson, AZ'],
    metrics: ['nightlights', 'parking'],
    period: 'Dec-Feb vs Jun-Aug (2023)',
    findings: [
      'Phoenix shows +42% winter activity increase',
      'Miami sees +38% seasonal population proxy',
      'Tampa records +35% winter nightlight intensity',
    ],
    image: '/images/snowbird-preview.png',
  },
  {
    id: 'covid',
    title: 'COVID-19 Impact Analysis',
    description:
      'Examine how urban activity collapsed in 2020 and recovered through 2022. This preset compares major metropolitan areas across the pandemic timeline.',
    regions: ['New York, NY', 'San Francisco, CA', 'Las Vegas, NV'],
    metrics: ['nightlights', 'parking', 'urban_density'],
    period: 'Jan 2019 vs Jan 2020 vs Jan 2021 vs Jan 2022',
    findings: [
      'Las Vegas: -45% activity drop in April 2020',
      'NYC: Nightlights down 25% at pandemic peak',
      'Recovery to pre-pandemic levels by mid-2022',
    ],
    image: '/images/covid-preview.png',
  },
  {
    id: 'urban-growth',
    title: 'Urban Growth: Phoenix 2015-2024',
    description:
      'Phoenix is one of Americas fastest-growing cities. This analysis tracks urban expansion using the full Sentinel-2 archive from 2015 to present.',
    regions: ['Phoenix Metro'],
    metrics: ['urban_density', 'ndvi'],
    period: '2015-2024 (Annual)',
    findings: [
      'Built-up area increased 23% since 2015',
      'Suburban sprawl visible in satellite imagery',
      'Vegetation (NDVI) declining at urban edges',
    ],
    image: '/images/phoenix-growth-preview.png',
  },
  {
    id: 'college-towns',
    title: 'College Town Seasonality',
    description:
      'University towns show distinct seasonal patterns driven by academic calendars. Compare activity during the school year (Sep-May) versus summer break.',
    regions: ['Austin, TX', 'Ann Arbor, MI', 'Boulder, CO'],
    metrics: ['nightlights', 'parking'],
    period: 'Academic Year vs Summer',
    findings: [
      'Ann Arbor: -22% summer activity drop',
      'Boulder: Significant seasonal variation',
      'Austin: More moderate due to city size',
    ],
    image: '/images/college-preview.png',
  },
  {
    id: 'tourism',
    title: 'Tourist Destination Patterns',
    description:
      'Tourism-driven economies show predictable seasonal activity fluctuations. Analyze peak vs off-peak patterns in major tourist destinations.',
    regions: ['Las Vegas, NV', 'Orlando, FL', 'Cancun, Mexico'],
    metrics: ['nightlights', 'parking'],
    period: 'Peak Season vs Off-Season',
    findings: [
      'Orlando: Summer peak from theme parks',
      'Las Vegas: Convention-driven patterns',
      'Clear correlation with school holiday periods',
    ],
    image: '/images/tourism-preview.png',
  },
];

export function Gallery() {
  return (
    <div className="gallery">
      <header className="gallery-header">
        <h1>Example Gallery</h1>
        <p>
          Explore curated analyses demonstrating the platform capabilities. Click any example
          to view the full analysis.
        </p>
      </header>

      <div className="presets-grid">
        {PRESETS.map((preset) => (
          <article key={preset.id} className="preset-card">
            <div className="preset-image">
              <div className="preset-image-placeholder">
                <span className="placeholder-icon">
                  {preset.id === 'snowbird' && '🦅'}
                  {preset.id === 'covid' && '🦠'}
                  {preset.id === 'urban-growth' && '🏗️'}
                  {preset.id === 'college-towns' && '🎓'}
                  {preset.id === 'tourism' && '✈️'}
                </span>
              </div>
            </div>

            <div className="preset-content">
              <h2>{preset.title}</h2>
              <p className="preset-description">{preset.description}</p>

              <div className="preset-details">
                <div className="detail-row">
                  <span className="detail-label">Regions:</span>
                  <span className="detail-value">{preset.regions.join(', ')}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Metrics:</span>
                  <span className="detail-value">
                    {preset.metrics.map((m) => m.replace('_', ' ')).join(', ')}
                  </span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">Period:</span>
                  <span className="detail-value">{preset.period}</span>
                </div>
              </div>

              <div className="preset-findings">
                <h4>Key Findings:</h4>
                <ul>
                  {preset.findings.map((finding, i) => (
                    <li key={i}>{finding}</li>
                  ))}
                </ul>
              </div>

              <Link to={`/regions?preset=${preset.id}`} className="btn btn-primary">
                Explore Analysis
              </Link>
            </div>
          </article>
        ))}
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
