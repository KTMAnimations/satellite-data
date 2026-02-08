type TelemetryEvent = {
  type: string;
  client_ts_ms?: number;
  path?: string;
  data?: Record<string, unknown> | null;
};

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';
const TELEMETRY_REGISTER_URL = `${API_BASE_URL}/telemetry/register`;
const TELEMETRY_EVENTS_URL = `${API_BASE_URL}/telemetry/events`;

const DEVICE_ID_KEY = 'satellite_device_id';
const INSTANCE_ID_KEY = 'satellite_instance_id';

function generateId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`;
}

function safeGet(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(storage: Storage, key: string, value: string): void {
  try {
    storage.setItem(key, value);
  } catch {
    // ignore
  }
}

function getOrCreateDeviceId(): string {
  const existing = safeGet(localStorage, DEVICE_ID_KEY);
  if (existing) return existing;
  const next = generateId();
  safeSet(localStorage, DEVICE_ID_KEY, next);
  return next;
}

function getOrCreateInstanceId(): string {
  const existing = safeGet(sessionStorage, INSTANCE_ID_KEY);
  if (existing) return existing;
  const next = generateId();
  safeSet(sessionStorage, INSTANCE_ID_KEY, next);
  return next;
}

async function postJson(url: string, body: unknown, { signal }: { signal?: AbortSignal } = {}): Promise<void> {
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
    credentials: 'same-origin',
  });
}

function trySendBeacon(url: string, body: unknown): boolean {
  try {
    if (typeof navigator === 'undefined' || typeof navigator.sendBeacon !== 'function') return false;
    const blob = new Blob([JSON.stringify(body)], { type: 'application/json' });
    return navigator.sendBeacon(url, blob);
  } catch {
    return false;
  }
}

export class TelemetryClient {
  private initialized = false;
  private registering: Promise<void> | null = null;
  private deviceId: string | null = null;
  private instanceId: string | null = null;
  private currentPath: string | null = null;
  private queue: TelemetryEvent[] = [];
  private flushTimer: number | null = null;
  private flushing = false;

  setCurrentPath(path: string) {
    this.currentPath = path;
  }

  init() {
    if (this.initialized) return;
    this.initialized = true;

    this.deviceId = getOrCreateDeviceId();
    this.instanceId = getOrCreateInstanceId();

    const meta = this.collectMeta();
    const path = this.currentPath ?? (typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : null);

    this.registering = postJson(TELEMETRY_REGISTER_URL, {
      instance_id: this.instanceId,
      device_id: this.deviceId,
      meta,
      path,
    }).catch(() => {
      // Best-effort; avoid breaking the app if telemetry fails.
    });

    document.addEventListener('visibilitychange', this.onVisibilityChange, { passive: true });
    window.addEventListener('focus', this.onFocus, { passive: true });
    window.addEventListener('blur', this.onBlur, { passive: true });
    window.addEventListener('pagehide', this.onPageHide, { passive: true });
  }

  log(type: string, data?: Record<string, unknown> | null, opts?: { path?: string; tsMs?: number }) {
    if (!type) return;
    const event: TelemetryEvent = {
      type,
      client_ts_ms: opts?.tsMs ?? Date.now(),
      path: opts?.path ?? this.currentPath ?? (typeof window !== 'undefined' ? `${window.location.pathname}${window.location.search}` : undefined),
      data: data ?? null,
    };

    this.queue.push(event);
    if (this.queue.length >= 25) {
      void this.flush();
      return;
    }
    this.scheduleFlush();
  }

  async flush() {
    if (this.flushing) return;
    if (!this.instanceId) return;
    if (this.queue.length === 0) return;

    this.flushing = true;
    const batch = this.queue.splice(0, this.queue.length);
    const payload = {
      instance_id: this.instanceId,
      device_id: this.deviceId,
      events: batch,
    };

    try {
      await this.registering;
      await postJson(TELEMETRY_EVENTS_URL, payload);
    } catch {
      // Drop on error (avoid infinite retry loops). The admin view is best-effort.
    } finally {
      this.flushing = false;
      if (this.queue.length > 0) this.scheduleFlush();
    }
  }

  private scheduleFlush() {
    if (this.flushTimer !== null) return;
    this.flushTimer = window.setTimeout(() => {
      this.flushTimer = null;
      void this.flush();
    }, 1500);
  }

  private collectMeta(): Record<string, unknown> {
    const nav = typeof navigator !== 'undefined' ? navigator : null;
    const screenObj = typeof window !== 'undefined' ? window.screen : null;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const navAny = nav as any;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const conn: any = navAny?.connection ?? navAny?.mozConnection ?? navAny?.webkitConnection;

    const timezone = (() => {
      try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
      } catch {
        return null;
      }
    })();

    return {
      userAgent: nav?.userAgent ?? null,
      language: nav?.language ?? null,
      languages: nav?.languages ?? null,
      platform: navAny?.platform ?? null,
      cookieEnabled: nav?.cookieEnabled ?? null,
      doNotTrack: navAny?.doNotTrack ?? null,
      hardwareConcurrency: navAny?.hardwareConcurrency ?? null,
      deviceMemory: navAny?.deviceMemory ?? null,
      timezone,
      timeZoneOffsetMinutes: new Date().getTimezoneOffset(),
      screen: screenObj
        ? {
            width: screenObj.width,
            height: screenObj.height,
            availWidth: screenObj.availWidth,
            availHeight: screenObj.availHeight,
            colorDepth: screenObj.colorDepth,
            pixelRatio: window.devicePixelRatio,
          }
        : null,
      connection: conn
        ? {
            effectiveType: conn.effectiveType,
            downlink: conn.downlink,
            rtt: conn.rtt,
            saveData: conn.saveData,
          }
        : null,
    };
  }

  private onVisibilityChange = () => {
    this.log('tab_visibility', { state: document.visibilityState });
  };

  private onFocus = () => {
    this.log('window_focus');
  };

  private onBlur = () => {
    this.log('window_blur');
  };

  private onPageHide = () => {
    if (!this.instanceId) return;
    if (this.queue.length === 0) return;
    const batch = this.queue.splice(0, this.queue.length);
    trySendBeacon(TELEMETRY_EVENTS_URL, {
      instance_id: this.instanceId,
      device_id: this.deviceId,
      events: batch,
    });
  };
}

export const telemetry = new TelemetryClient();

