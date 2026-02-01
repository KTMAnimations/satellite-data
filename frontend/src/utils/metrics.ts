import type { MetricType } from '../types';
import { METRIC_VALUE_RANGES } from '../config/metricRanges';

export function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

export function getMetricValueRange(metric: MetricType): [number, number] {
  return METRIC_VALUE_RANGES[metric];
}

export function getRangeWidth(min: number, max: number): number | null {
  const width = max - min;
  if (!Number.isFinite(width) || width === 0) return null;
  return width;
}

export function normalizeValueInRange(
  value: number,
  min: number,
  max: number,
  options?: { clamp?: boolean }
): number | null {
  if (!Number.isFinite(value) || !Number.isFinite(min) || !Number.isFinite(max)) return null;
  const width = getRangeWidth(min, max);
  if (!width) return null;
  const normalized = (value - min) / width;
  return options?.clamp ? clamp01(normalized) : normalized;
}

export function normalizeMetricValue(
  metric: MetricType,
  value: number,
  options?: { clamp?: boolean }
): number | null {
  const [min, max] = getMetricValueRange(metric);
  return normalizeValueInRange(value, min, max, options);
}

/**
 * Unit-invariant percent change for charting.
 *
 * Computes delta as a percentage of the full metric range:
 *   (to - from) / (max - min) * 100
 *
 * This is invariant under affine unit transforms (e.g., °C↔°F) when the
 * corresponding min/max range is transformed consistently.
 */
export function computeDeltaPercentOfRange(
  fromValue: number,
  toValue: number,
  min: number,
  max: number
): number | null {
  if (!Number.isFinite(fromValue) || !Number.isFinite(toValue)) return null;
  const width = getRangeWidth(min, max);
  if (!width) return null;
  return ((toValue - fromValue) / width) * 100;
}

export function computeMetricDeltaPercentOfRange(
  metric: MetricType,
  fromValue: number,
  toValue: number
): number | null {
  const [min, max] = getMetricValueRange(metric);
  return computeDeltaPercentOfRange(fromValue, toValue, min, max);
}

