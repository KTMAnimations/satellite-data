import { describe, expect, it } from 'vitest';
import { formatDateTimeInClientTimeZone, parseIsoAsUtcWhenNaive } from '../../utils/dateTime';

describe('dateTime utils', () => {
  it('parses timezone-naive ISO strings as UTC', () => {
    const parsed = parseIsoAsUtcWhenNaive('2026-02-09T12:34:56');
    expect(parsed).not.toBeNull();
    expect(parsed?.toISOString()).toBe('2026-02-09T12:34:56.000Z');
  });

  it('parses timezone-naive strings with a space separator as UTC', () => {
    const parsed = parseIsoAsUtcWhenNaive('2026-02-09 12:34:56');
    expect(parsed).not.toBeNull();
    expect(parsed?.toISOString()).toBe('2026-02-09T12:34:56.000Z');
  });

  it('preserves explicit timezone offsets', () => {
    const parsed = parseIsoAsUtcWhenNaive('2026-02-09T12:34:56+02:00');
    expect(parsed).not.toBeNull();
    expect(parsed?.toISOString()).toBe('2026-02-09T10:34:56.000Z');
  });

  it('returns fallback values for empty or invalid inputs', () => {
    expect(formatDateTimeInClientTimeZone(null)).toBe('—');
    expect(formatDateTimeInClientTimeZone(undefined)).toBe('—');
    expect(formatDateTimeInClientTimeZone('not-a-date')).toBe('not-a-date');
  });
});
