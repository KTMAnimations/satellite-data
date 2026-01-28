// Utilities for working with metric date strings coming from the API.
// We avoid `new Date("YYYY-MM-DD")` because it is parsed as UTC and can shift a day
// when displayed/aggregated in local time.

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

export function formatDateYYYYMMDD(date: Date | null | undefined): string | null {
  if (!date) return null;
  if (Number.isNaN(date.getTime())) return null;
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function firstMondayOfYear(year: number): Date {
  const jan1 = new Date(year, 0, 1);
  const day = jan1.getDay(); // 0 (Sun) .. 6 (Sat)
  const daysUntilMonday = (8 - day) % 7; // 0 if Monday
  return new Date(year, 0, 1 + daysUntilMonday);
}

// Parse date bucket strings used by the metrics API.
// Supported:
// - "YYYY-MM" (monthly)
// - "YYYY-MM-DD" (daily/weekly)
// - legacy "YYYY-W##" (Python %W week number; week 00 may exist)
export function parseMetricDate(dateStr: string): Date | null {
  const isoMatch = dateStr.match(/^(\d{4})-(\d{2})(?:-(\d{2}))?$/);
  if (isoMatch) {
    const year = Number(isoMatch[1]);
    const month = Number(isoMatch[2]);
    const day = isoMatch[3] ? Number(isoMatch[3]) : 1;
    if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
    const parsed = new Date(year, month - 1, day);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  const weekMatch = dateStr.match(/^(\d{4})-W(\d{2})$/);
  if (weekMatch) {
    const year = Number(weekMatch[1]);
    const week = Number(weekMatch[2]);
    if (!Number.isFinite(year) || !Number.isFinite(week)) return null;

    if (week <= 0) {
      const jan1 = new Date(year, 0, 1);
      return Number.isNaN(jan1.getTime()) ? null : jan1;
    }

    const firstMonday = firstMondayOfYear(year);
    const parsed = new Date(firstMonday);
    parsed.setDate(firstMonday.getDate() + (week - 1) * 7);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  return null;
}
