import { describe, expect, it } from 'vitest';
import { estimateBucketCount, getRecommendedGranularity } from '../../config/metrics';

describe('metrics granularity helpers', () => {
  it('estimates daily buckets (inclusive)', () => {
    expect(estimateBucketCount(new Date(2024, 0, 1), new Date(2024, 0, 1), 'daily')).toBe(1);
    expect(estimateBucketCount(new Date(2024, 0, 1), new Date(2024, 0, 3), 'daily')).toBe(3);
  });

  it('estimates weekly buckets (every 7 days, starting at start)', () => {
    expect(estimateBucketCount(new Date(2024, 0, 1), new Date(2024, 0, 7), 'weekly')).toBe(1);
    expect(estimateBucketCount(new Date(2024, 0, 1), new Date(2024, 0, 8), 'weekly')).toBe(2);
  });

  it('estimates monthly buckets (start of month)', () => {
    expect(estimateBucketCount(new Date(2024, 0, 15), new Date(2024, 0, 30), 'monthly')).toBe(1);
    expect(estimateBucketCount(new Date(2024, 0, 15), new Date(2024, 1, 1), 'monthly')).toBe(2);
  });

  it('picks the finest supported granularity that fits the point limit', () => {
    const shortRange = { start: new Date(2024, 0, 1), end: new Date(2024, 0, 31) };
    expect(getRecommendedGranularity('nightlights', shortRange)).toBe('daily');
    expect(getRecommendedGranularity('ndvi', shortRange)).toBe('weekly');

    const longRange = { start: new Date(2010, 0, 1), end: new Date(2016, 0, 1) };
    expect(getRecommendedGranularity('nightlights', longRange)).toBe('monthly');

    // Force a coarser pick with an artificially small maxPoints limit.
    expect(getRecommendedGranularity('ndvi', shortRange, 2)).toBe('monthly');
  });
});

