import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeasonalBarChart } from '../../components/Charts/SeasonalBarChart';

// Mock D3
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

describe('SeasonalBarChart', () => {
  const mockData = {
    winter: {
      ndvi: 0.35,
      nightlights: 45.2,
    },
    summer: {
      ndvi: 0.62,
      nightlights: 38.7,
    },
  };

  it('renders without crashing', () => {
    const { container } = render(
      <SeasonalBarChart
        data={mockData}
        metrics={['ndvi', 'nightlights']}
      />
    );
    expect(container).toBeTruthy();
  });

  it('shows seasonal labels', () => {
    render(
      <SeasonalBarChart
        data={mockData}
        metrics={['ndvi']}
      />
    );

    expect(screen.getByText(/Winter/i)).toBeInTheDocument();
    expect(screen.getByText(/Summer/i)).toBeInTheDocument();
  });

  it('displays header with comparison title', () => {
    render(
      <SeasonalBarChart
        data={mockData}
        metrics={['ndvi']}
      />
    );

    expect(screen.getByText(/Seasonal Comparison/i)).toBeInTheDocument();
  });

  it('renders chart container', () => {
    const { container } = render(
      <SeasonalBarChart
        data={mockData}
        metrics={['ndvi']}
      />
    );

    const chartContainer = container.querySelector('.seasonal-bar-chart');
    expect(chartContainer).toBeInTheDocument();
  });
});
