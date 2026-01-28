import { describe, it, expect } from 'vitest';
import { formatDateYYYYMMDD, parseMetricDate } from '../../utils/dates';

describe('dates utils', () => {
  it('parses monthly buckets (YYYY-MM) as local dates', () => {
    const d = parseMetricDate('2024-01');
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2024);
    expect(d!.getMonth()).toBe(0);
    expect(d!.getDate()).toBe(1);
  });

  it('parses daily buckets (YYYY-MM-DD) as local dates', () => {
    const d = parseMetricDate('2024-01-15');
    expect(d).not.toBeNull();
    expect(d!.getFullYear()).toBe(2024);
    expect(d!.getMonth()).toBe(0);
    expect(d!.getDate()).toBe(15);
  });

  it('formats local dates to YYYY-MM-DD', () => {
    expect(formatDateYYYYMMDD(new Date(2024, 0, 5))).toBe('2024-01-05');
  });

  it('supports legacy weekly buckets (YYYY-W##)', () => {
    // 2024-01-01 is a Monday, so week 01 starts on Jan 1.
    const week1 = parseMetricDate('2024-W01');
    const week2 = parseMetricDate('2024-W02');

    expect(week1).not.toBeNull();
    expect(week1!.getFullYear()).toBe(2024);
    expect(week1!.getMonth()).toBe(0);
    expect(week1!.getDate()).toBe(1);

    expect(week2).not.toBeNull();
    expect(week2!.getFullYear()).toBe(2024);
    expect(week2!.getMonth()).toBe(0);
    expect(week2!.getDate()).toBe(8);
  });
});

