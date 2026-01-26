import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TimeSeriesChart } from '../../components/Charts/TimeSeriesChart';

// Mock D3 to prevent canvas rendering issues
vi.mock('d3', async () => {
  const actual = await vi.importActual('d3');
  return {
    ...actual,
    select: vi.fn().mockReturnValue({
      selectAll: vi.fn().mockReturnThis(),
      remove: vi.fn().mockReturnThis(),
      append: vi.fn().mockReturnThis(),
      attr: vi.fn().mockReturnThis(),
      style: vi.fn().mockReturnThis(),
      text: vi.fn().mockReturnThis(),
      datum: vi.fn().mockReturnThis(),
      call: vi.fn().mockReturnThis(),
      on: vi.fn().mockReturnThis(),
    }),
  };
});

describe('TimeSeriesChart', () => {
  const mockData = [
    { date: '2024-01', ndvi: 0.45, nightlights: 32.5 },
    { date: '2024-02', ndvi: 0.48, nightlights: 35.2 },
    { date: '2024-03', ndvi: 0.52, nightlights: 38.1 },
  ];

  it('renders without crashing', () => {
    const { container } = render(
      <TimeSeriesChart
        data={mockData}
        metrics={['ndvi']}
      />
    );
    expect(container).toBeTruthy();
  });

  it('shows header with metric label', () => {
    render(
      <TimeSeriesChart
        data={mockData}
        metrics={['ndvi']}
      />
    );

    expect(screen.getByText(/NDVI/i)).toBeInTheDocument();
  });

  it('displays multiple metrics', () => {
    render(
      <TimeSeriesChart
        data={mockData}
        metrics={['ndvi', 'nightlights']}
      />
    );

    expect(screen.getByText(/NDVI/i)).toBeInTheDocument();
    expect(screen.getByText(/Nighttime Lights/i)).toBeInTheDocument();
  });

  it('renders chart container', () => {
    const { container } = render(
      <TimeSeriesChart
        data={mockData}
        metrics={['ndvi']}
      />
    );

    const chartContainer = container.querySelector('.time-series-chart');
    expect(chartContainer).toBeInTheDocument();
  });

  it('handles empty data gracefully', () => {
    const { container } = render(
      <TimeSeriesChart
        data={[]}
        metrics={['ndvi']}
      />
    );

    expect(container).toBeTruthy();
  });
});
