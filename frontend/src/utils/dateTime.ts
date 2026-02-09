const CLIENT_TIME_ZONE = (() => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
})();

export function formatDateObjectInClientTimeZone(date: Date): string {
  if (CLIENT_TIME_ZONE) return date.toLocaleString(undefined, { timeZone: CLIENT_TIME_ZONE });
  return date.toLocaleString();
}

export function parseIsoAsUtcWhenNaive(iso: string): Date | null {
  const trimmed = iso.trim();
  if (!trimmed) return null;

  const withIsoSeparator = trimmed.replace(' ', 'T');
  const hasExplicitZone = /(?:[zZ]|[+-]\d{2}:\d{2}|[+-]\d{4})$/.test(withIsoSeparator);
  const candidate = hasExplicitZone ? withIsoSeparator : `${withIsoSeparator}Z`;
  const parsed = new Date(candidate);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

export function formatDateTimeInClientTimeZone(iso: string | null | undefined): string {
  if (!iso) return '—';
  const parsed = parseIsoAsUtcWhenNaive(iso);
  if (!parsed) return iso;
  return formatDateObjectInClientTimeZone(parsed);
}
