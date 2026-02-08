import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeasonalBarChart } from '../../components/Charts/SeasonalBarChart';
import { emptyMetricRecord } from '../../config/metrics';

// Mock D3
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
    filter: vi.fn().mockReturnThis(),
    enter: vi.fn().mockReturnThis(),
    data: vi.fn().mockReturnThis(),
  };
  return {
    ...actual,
    select: vi.fn().mockReturnValue(stubSelection),
  };
});

describe('SeasonalBarChart', () => {
  const emptyAverage = emptyMetricRecord<number | null>(null);

  it('shows empty-state message when no seasonal data is available', () => {
    render(
      <SeasonalBarChart
        data={{
          winter_avg: { ...emptyAverage },
          summer_avg: { ...emptyAverage },
          change_pct: { ...emptyAverage },
        }}
      />
    );

    expect(screen.getByText('No seasonal comparison available')).toBeInTheDocument();
  });

  it('renders an SVG when seasonal data exists', () => {
    const { container } = render(
      <SeasonalBarChart
        data={{
          winter_avg: { ...emptyAverage, ndvi: 0.35, nightlights: 45.2 },
          summer_avg: { ...emptyAverage, ndvi: 0.62, nightlights: 38.7 },
          change_pct: { ...emptyAverage, ndvi: 10, nightlights: -5 },
        }}
      />
    );

    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(screen.queryByText('No seasonal comparison available')).not.toBeInTheDocument();
  });
});
