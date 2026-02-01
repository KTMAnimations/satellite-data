type PointerLikeEvent = {
  clientX: number;
  clientY: number;
};

const GLOBAL_TOOLTIP_ID = 'chart-tooltip-global';
const VIEWPORT_PADDING_PX = 12;

function clamp(value: number, min: number, max: number) {
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

export function ensureGlobalChartTooltip(): HTMLDivElement | null {
  if (typeof document === 'undefined') return null;

  const existing = document.getElementById(GLOBAL_TOOLTIP_ID);
  if (existing && existing instanceof HTMLDivElement) return existing;

  if (existing) existing.remove();

  const tooltip = document.createElement('div');
  tooltip.id = GLOBAL_TOOLTIP_ID;
  tooltip.className = 'chart-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  tooltip.style.opacity = '0';
  document.body.appendChild(tooltip);
  return tooltip;
}

export function showGlobalChartTooltip(
  event: PointerLikeEvent,
  html: string,
  opts: { offsetX?: number; offsetY?: number } = {}
) {
  const tooltip = ensureGlobalChartTooltip();
  if (!tooltip || typeof window === 'undefined') return;

  const offsetX = opts.offsetX ?? 12;
  const offsetY = opts.offsetY ?? -12;

  tooltip.innerHTML = html;
  tooltip.style.opacity = '1';

  const rect = tooltip.getBoundingClientRect();
  const maxLeft = Math.max(VIEWPORT_PADDING_PX, window.innerWidth - rect.width - VIEWPORT_PADDING_PX);
  const maxTop = Math.max(VIEWPORT_PADDING_PX, window.innerHeight - rect.height - VIEWPORT_PADDING_PX);

  const left = clamp(event.clientX + offsetX, VIEWPORT_PADDING_PX, maxLeft);
  const top = clamp(event.clientY + offsetY, VIEWPORT_PADDING_PX, maxTop);

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

export function hideGlobalChartTooltip() {
  if (typeof document === 'undefined') return;
  const tooltip = document.getElementById(GLOBAL_TOOLTIP_ID);
  if (!tooltip) return;
  tooltip.style.opacity = '0';
}

