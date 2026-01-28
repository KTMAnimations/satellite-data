import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SmallMultiples } from '../../components/Charts/SmallMultiples';

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
    each: vi.fn().mockReturnThis(),
    node: vi.fn().mockReturnValue({ getTotalLength: () => 100 }),
    data: vi.fn().mockReturnThis(),
    enter: vi.fn().mockReturnThis(),
  };
  return {
    ...actual,
    select: vi.fn().mockReturnValue(stubSelection),
  };
});

describe('SmallMultiples', () => {
  const mockRegions = [
    {
      regionId: 'phoenix',
      regionName: 'Phoenix, AZ',
      data: [
        { date: '2024-01', value: 0.45 },
        { date: '2024-02', value: 0.48 },
      ],
    },
    {
      regionId: 'miami',
      regionName: 'Miami, FL',
      data: [
        { date: '2024-01', value: 0.55 },
        { date: '2024-02', value: 0.58 },
      ],
    },
    {
      regionId: 'tampa',
      regionName: 'Tampa, FL',
      data: [
        { date: '2024-01', value: 0.42 },
        { date: '2024-02', value: 0.46 },
      ],
    },
  ];

  it('renders without crashing', () => {
    const { container } = render(
      <SmallMultiples
        regions={mockRegions}
        metric="ndvi"
      />
    );
    expect(container).toBeTruthy();
  });

  it('shows region count badge', () => {
    render(
      <SmallMultiples
        regions={mockRegions}
        metric="ndvi"
      />
    );

    expect(screen.getByText('3 regions')).toBeInTheDocument();
  });

  it('displays metric label in header', () => {
    render(
      <SmallMultiples
        regions={mockRegions}
        metric="ndvi"
      />
    );

    expect(screen.getByText(/NDVI Comparison/i)).toBeInTheDocument();
  });

  it('renders grid container', () => {
    const { container } = render(
      <SmallMultiples
        regions={mockRegions}
        metric="ndvi"
        columns={3}
      />
    );

    const grid = container.querySelector('.small-multiples-grid');
    expect(grid).toBeInTheDocument();
  });

  it('handles click callback', () => {
    const handleClick = vi.fn();
    const { container } = render(
      <SmallMultiples
        regions={mockRegions}
        metric="ndvi"
        onRegionClick={handleClick}
      />
    );
    expect(container).toBeTruthy();
  });

  it('handles empty regions array', () => {
    render(
      <SmallMultiples
        regions={[]}
        metric="ndvi"
      />
    );

    expect(screen.getByText('0 regions')).toBeInTheDocument();
  });
});
