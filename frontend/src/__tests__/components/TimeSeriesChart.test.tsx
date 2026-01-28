import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TimeSeriesChart } from '../../components/Charts/TimeSeriesChart';

// Mock D3 to prevent canvas rendering issues
vi.mock('d3', async () => {
  const actual = await vi.importActual('d3');
  const stubSelection = {
    selectAll: vi.fn().mockReturnThis(),
    interrupt: vi.fn().mockReturnThis(),
    remove: vi.fn().mockReturnThis(),
    append: vi.fn().mockReturnThis(),
    attr: vi.fn().mockReturnThis(),
    style: vi.fn().mockReturnThis(),
    text: vi.fn().mockReturnThis(),
    datum: vi.fn().mockReturnThis(),
    call: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
    data: vi.fn().mockReturnThis(),
    enter: vi.fn().mockReturnThis(),
  };
  return {
    ...actual,
    select: vi.fn().mockReturnValue(stubSelection),
  };
});

describe('TimeSeriesChart', () => {
  const emptyMetric = { unit: '', data: [] };
  const baseData = {
    nightlights: { ...emptyMetric },
    ndvi: { ...emptyMetric },
    urban_density: { ...emptyMetric },
    parking: { ...emptyMetric },
    land_cover: { ...emptyMetric },
    surface_water: { ...emptyMetric },
    active_fire: { ...emptyMetric },
    no2: { ...emptyMetric },
    temperature: { ...emptyMetric },
    precipitation: { ...emptyMetric },
    aerosol: { ...emptyMetric },
    cropland: { ...emptyMetric },
    evapotranspiration: { ...emptyMetric },
    soil_moisture: { ...emptyMetric },
    impervious: { ...emptyMetric },
    fire_historical: { ...emptyMetric },
    canopy_height: { ...emptyMetric },
  } as const;

  it('shows empty-state message when selected metrics have no data', () => {
    const { container } = render(
      <TimeSeriesChart
        data={{ ...baseData }}
        selectedMetrics={['ndvi']}
      />
    );

    expect(container.querySelector('.chart-tooltip')).not.toBeInTheDocument();
    expect(screen.getByText('No data collected for this region')).toBeInTheDocument();
  });

  it('renders an SVG and tooltip when data exists', () => {
    const { container } = render(
      <TimeSeriesChart
        data={{
          ...baseData,
          ndvi: {
            unit: 'index (-1 to 1)',
            data: [
              { date: '2024-01-01', value: 0.45 },
              { date: '2024-02-01', value: 0.48 },
            ],
          },
          nightlights: {
            unit: 'nW/cm²/sr',
            data: [
              { date: '2024-01-01', value: 32.5 },
              { date: '2024-02-01', value: 35.2 },
            ],
          },
        }}
        selectedMetrics={['ndvi', 'nightlights']}
      />
    );

    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(container.querySelector('.chart-tooltip')).toBeInTheDocument();
  });
});
