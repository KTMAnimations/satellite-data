import { describe, it, expect } from 'vitest';
import { computeDeltaPercentOfRange, normalizeValueInRange } from '../../utils/metrics';

describe('metrics utils', () => {
  it('computes unit-invariant percent change for affine transforms (°C↔°F)', () => {
    const cMin = -30;
    const cMax = 45;
    const toF = (c: number) => (c * 9) / 5 + 32;

    const fMin = toF(cMin);
    const fMax = toF(cMax);

    const winterC = 0;
    const summerC = 20;

    const winterF = toF(winterC);
    const summerF = toF(summerC);

    const pctC = computeDeltaPercentOfRange(winterC, summerC, cMin, cMax);
    const pctF = computeDeltaPercentOfRange(winterF, summerF, fMin, fMax);

    expect(pctC).not.toBeNull();
    expect(pctF).not.toBeNull();
    expect(pctF!).toBeCloseTo(pctC!, 10);
  });

  it('normalizes values consistently when clamped', () => {
    expect(normalizeValueInRange(0, 0, 100, { clamp: true })).toBeCloseTo(0, 10);
    expect(normalizeValueInRange(50, 0, 100, { clamp: true })).toBeCloseTo(0.5, 10);
    expect(normalizeValueInRange(100, 0, 100, { clamp: true })).toBeCloseTo(1, 10);
    expect(normalizeValueInRange(-10, 0, 100, { clamp: true })).toBeCloseTo(0, 10);
    expect(normalizeValueInRange(110, 0, 100, { clamp: true })).toBeCloseTo(1, 10);
  });
});

