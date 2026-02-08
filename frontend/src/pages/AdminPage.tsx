import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { useStore, type DaytimeBasemap } from '../store';
import type {
  AdminInstanceDetailResponse,
  AdminInstanceEventsResponse,
  AdminInstanceSummary,
  AdminIpDetailResponse,
  AdminIpListResponse,
  AdminIpSummary,
  AdminTelemetryEvent,
  MetricType,
} from '../types';
import './AdminPage.css';

type AdminAuth = {
  token: string;
  setToken: (next: string) => void;
};

const AdminAuthContext = createContext<AdminAuth | null>(null);

function useAdminAuth(): AdminAuth {
  const ctx = useContext(AdminAuthContext);
  if (!ctx) throw new Error('useAdminAuth must be used within AdminAuthContext.Provider');
  return ctx;
}

const ADMIN_TOKEN_STORAGE_KEY = 'satellite_admin_token';

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function formatEventTimestamp(event: AdminTelemetryEvent): string {
  if (event.client_ts_ms !== null && event.client_ts_ms !== undefined) {
    const d = new Date(event.client_ts_ms);
    if (!Number.isNaN(d.getTime())) return d.toLocaleString();
  }
  return formatDateTime(event.received_at);
}

function formatDeltaMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—';
  if (!Number.isFinite(ms)) return '—';
  const sign = ms < 0 ? '-' : '+';
  const abs = Math.abs(ms);
  if (abs < 1000) return `${sign}${Math.round(abs)}ms`;
  if (abs < 60_000) return `${sign}${(abs / 1000).toFixed(2)}s`;
  if (abs < 3_600_000) return `${sign}${(abs / 60_000).toFixed(2)}m`;
  return `${sign}${(abs / 3_600_000).toFixed(2)}h`;
}

function isMetricType(value: unknown): value is MetricType {
  return (
    typeof value === 'string'
    && [
      'ndvi',
      'nightlights',
      'surface_water',
      'no2',
      'temperature',
      'precipitation',
      'aerosol',
      'cropland',
      'evapotranspiration',
      'soil_moisture',
      'impervious',
      'canopy_height',
      'forest_loss_year',
      'snow_cover',
      'travel_time_to_cities',
    ].includes(value)
  );
}

function buildMapJumpUrl(event: AdminTelemetryEvent): string | null {
  const data = event.data ?? {};
  const centerRaw = (data as Record<string, unknown>).center;
  const zoomRaw = (data as Record<string, unknown>).zoom;
  if (!Array.isArray(centerRaw) || centerRaw.length !== 2) return null;

  const lat = Number(centerRaw[0]);
  const lng = Number(centerRaw[1]);
  const zoom = Number(zoomRaw);
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || !Number.isFinite(zoom)) return null;

  const metricRaw = (data as Record<string, unknown>).metric;
  const metric = isMetricType(metricRaw) ? metricRaw : null;

  const base = (import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/');
  const url = new URL(`${base}map`, window.location.origin);
  url.searchParams.set('lat', String(lat));
  url.searchParams.set('lng', String(lng));
  url.searchParams.set('zoom', String(zoom));
  if (metric) url.searchParams.set('metric', metric);
  return url.toString();
}

function AdminHeader() {
  const { token, setToken } = useAdminAuth();
  const daytimeBasemap = useStore((state) => state.daytimeBasemap);
  const setDaytimeBasemap = useStore((state) => state.setDaytimeBasemap);
  const [draft, setDraft] = useState(token);
  const maptilerAvailable = (import.meta.env.VITE_MAPTILER_KEY ?? '').trim().length > 0;

  useEffect(() => {
    setDraft(token);
  }, [token]);

  return (
    <div className="admin-header instrument-panel">
      <div className="admin-header-row">
        <div className="admin-title">
          <div className="admin-kicker">Admin</div>
          <div className="admin-heading">Access & Activity Log</div>
        </div>

        <div className="admin-auth">
          <label className="admin-auth-label" htmlFor="admin-token">ADMIN_TOKEN</label>
          <input
            id="admin-token"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="(optional in development)"
            className="admin-auth-input"
            autoComplete="off"
            spellCheck={false}
          />
          <button
            type="button"
            className="btn btn-outline"
            onClick={() => {
              setToken(draft.trim());
            }}
          >
            Apply
          </button>
        </div>

        <div className="admin-map-settings">
          <label className="admin-auth-label" htmlFor="admin-day-basemap">Day Basemap</label>
          <select
            id="admin-day-basemap"
            className="admin-map-select"
            value={daytimeBasemap}
            onChange={(e) => {
              const next = e.target.value as DaytimeBasemap;
              if (next === 'maptiler_osm' && !maptilerAvailable) return;
              setDaytimeBasemap(next);
            }}
          >
            <option value="carto_light">CARTO Light</option>
            <option value="maptiler_osm" disabled={!maptilerAvailable}>MapTiler OpenStreetMap</option>
          </select>
          {!maptilerAvailable && <span className="admin-muted">MapTiler requires `VITE_MAPTILER_KEY`.</span>}
        </div>
      </div>
      <div className="admin-header-links">
        <Link to="/admin" className="btn btn-ghost">IP List</Link>
      </div>
    </div>
  );
}

function IpListView() {
  const { token } = useAdminAuth();
  const navigate = useNavigate();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<AdminIpListResponse>({
    queryKey: ['admin', 'ips', token],
    queryFn: ({ signal }) => api.adminListIps({ limit: 2000, offset: 0 }, token, { signal }),
  });

  return (
    <div className="admin-body instrument-panel">
      <div className="admin-section-title-row">
        <h3>IP Addresses</h3>
        <button type="button" className="btn btn-outline" disabled={isFetching} onClick={() => void refetch()}>
          Refresh
        </button>
      </div>

      {isLoading && <div className="admin-muted">Loading…</div>}
      {isError && (
        <div className="admin-error">
          Failed to load IPs: {(error as Error)?.message ?? String(error)}
        </div>
      )}

      {data?.ips?.length ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>IP</th>
                <th>First seen</th>
                <th>Last seen</th>
                <th>Instances</th>
                <th>Events</th>
              </tr>
            </thead>
            <tbody>
              {data.ips.map((ip: AdminIpSummary) => (
                <tr
                  key={ip.ip_address}
                  className="admin-row-clickable"
                  onClick={() => navigate(`/admin/ip/${encodeURIComponent(ip.ip_address)}`)}
                >
                  <td className="mono">{ip.ip_address}</td>
                  <td>{formatDateTime(ip.first_seen_at)}</td>
                  <td>{formatDateTime(ip.last_seen_at)}</td>
                  <td>{ip.instance_count}</td>
                  <td>{ip.event_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !isLoading && <div className="admin-muted">No telemetry yet. Load the site in another browser to generate activity.</div>
      )}
    </div>
  );
}

function IpDetailView() {
  const { token } = useAdminAuth();
  const { ip: ipParam } = useParams<{ ip: string }>();
  const ipAddress = useMemo(() => decodeURIComponent(ipParam ?? ''), [ipParam]);
  const navigate = useNavigate();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<AdminIpDetailResponse>({
    queryKey: ['admin', 'ip', ipAddress, token],
    queryFn: ({ signal }) => api.adminGetIpDetail(ipAddress, token, { signal }),
    enabled: Boolean(ipAddress),
  });

  return (
    <div className="admin-body instrument-panel">
      <div className="admin-section-title-row">
        <h3>IP Detail</h3>
        <div className="admin-actions">
          <button type="button" className="btn btn-outline" onClick={() => navigate(-1)}>Back</button>
          <button type="button" className="btn btn-outline" disabled={isFetching} onClick={() => void refetch()}>
            Refresh
          </button>
        </div>
      </div>

      {isLoading && <div className="admin-muted">Loading…</div>}
      {isError && <div className="admin-error">Failed: {(error as Error)?.message ?? String(error)}</div>}

      {data && (
        <>
          <div className="admin-kv">
            <div><span className="admin-k">IP</span> <span className="mono">{data.ip.ip_address}</span></div>
            <div><span className="admin-k">First seen</span> {formatDateTime(data.ip.first_seen_at)}</div>
            <div><span className="admin-k">Last seen</span> {formatDateTime(data.ip.last_seen_at)}</div>
            <div><span className="admin-k">Instances</span> {data.ip.instance_count}</div>
            <div><span className="admin-k">Events</span> {data.ip.event_count}</div>
          </div>

          <h4 className="admin-subtitle">Instances</h4>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Instance</th>
                  <th>Last path</th>
                  <th>Last seen</th>
                  <th>Events</th>
                  <th>User agent</th>
                </tr>
              </thead>
              <tbody>
                {data.instances.map((inst: AdminInstanceSummary) => (
                  <tr
                    key={inst.instance_id}
                    className="admin-row-clickable"
                    onClick={() => navigate(`/admin/instance/${inst.instance_id}`)}
                  >
                    <td className="mono">{inst.instance_id}</td>
                    <td className="mono admin-ellipsis">{inst.last_path ?? '—'}</td>
                    <td>{formatDateTime(inst.last_seen_at)}</td>
                    <td>{inst.event_count}</td>
                    <td className="admin-ellipsis">{inst.user_agent ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function InstanceDetailView() {
  const { token } = useAdminAuth();
  const { instanceId } = useParams<{ instanceId: string }>();
  const navigate = useNavigate();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<AdminInstanceDetailResponse>({
    queryKey: ['admin', 'instance', instanceId, token],
    queryFn: ({ signal }) => api.adminGetInstanceDetail(instanceId!, token, { signal }),
    enabled: Boolean(instanceId),
  });

  return (
    <div className="admin-body instrument-panel">
      <div className="admin-section-title-row">
        <h3>Instance</h3>
        <div className="admin-actions">
          <button type="button" className="btn btn-outline" onClick={() => navigate(-1)}>Back</button>
          <button type="button" className="btn btn-outline" disabled={isFetching} onClick={() => void refetch()}>
            Refresh
          </button>
          {instanceId && (
            <Link to={`/admin/instance/${instanceId}/log`} className="btn btn-primary">
              View Chronological Log
            </Link>
          )}
        </div>
      </div>

      {isLoading && <div className="admin-muted">Loading…</div>}
      {isError && <div className="admin-error">Failed: {(error as Error)?.message ?? String(error)}</div>}

      {data && (
        <>
          <div className="admin-kv">
            <div><span className="admin-k">Instance</span> <span className="mono">{data.instance_id}</span></div>
            <div><span className="admin-k">Device</span> <span className="mono">{data.device_id ?? '—'}</span></div>
            <div><span className="admin-k">IP</span> <span className="mono">{data.ip_address}</span></div>
            <div><span className="admin-k">First seen</span> {formatDateTime(data.first_seen_at)}</div>
            <div><span className="admin-k">Last seen</span> {formatDateTime(data.last_seen_at)}</div>
            <div><span className="admin-k">Last path</span> <span className="mono">{data.last_path ?? '—'}</span></div>
            <div><span className="admin-k">Total events</span> {data.total_events}</div>
            <div><span className="admin-k">Distinct paths</span> {data.distinct_paths}</div>
          </div>

          <h4 className="admin-subtitle">Browser / Agent</h4>
          <div className="admin-pre">
            <pre>{JSON.stringify({ user_agent: data.user_agent, accept_language: data.accept_language, ...data.meta }, null, 2)}</pre>
          </div>

          <h4 className="admin-subtitle">Activity Summary</h4>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Event type</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.event_type_counts).map(([eventType, count]) => (
                  <tr key={eventType}>
                    <td className="mono">{eventType}</td>
                    <td>{count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function InstanceLogView() {
  const { token } = useAdminAuth();
  const { instanceId } = useParams<{ instanceId: string }>();
  const navigate = useNavigate();

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<AdminInstanceEventsResponse>({
    queryKey: ['admin', 'instance', instanceId, 'events', token],
    queryFn: ({ signal }) => api.adminListInstanceEvents(instanceId!, { limit: 5000, offset: 0 }, token, { signal }),
    enabled: Boolean(instanceId),
  });

  const eventsWithDelta = useMemo(() => {
    const events = data?.events ?? [];
    return events.map((event, idx) => {
      const prev = events[idx - 1];
      const deltaMs =
        event.client_ts_ms !== null
        && event.client_ts_ms !== undefined
        && prev?.client_ts_ms !== null
        && prev?.client_ts_ms !== undefined
          ? event.client_ts_ms - prev.client_ts_ms
          : null;
      return { event, deltaMs };
    });
  }, [data?.events]);

  return (
    <div className="admin-body instrument-panel">
      <div className="admin-section-title-row">
        <h3>Chronological Log</h3>
        <div className="admin-actions">
          <button type="button" className="btn btn-outline" onClick={() => navigate(-1)}>Back</button>
          <button type="button" className="btn btn-outline" disabled={isFetching} onClick={() => void refetch()}>
            Refresh
          </button>
        </div>
      </div>

      {isLoading && <div className="admin-muted">Loading…</div>}
      {isError && <div className="admin-error">Failed: {(error as Error)?.message ?? String(error)}</div>}

      {eventsWithDelta.length ? (
        <div className="admin-log">
          {eventsWithDelta.map(({ event, deltaMs }) => {
            const jumpUrl = buildMapJumpUrl(event);
            return (
              <div key={event.id} className="admin-log-row">
                <div className="admin-log-meta">
                  <div className="admin-log-ts">{formatEventTimestamp(event)}</div>
                  <div className="admin-log-delta">{formatDeltaMs(deltaMs)}</div>
                </div>
                <div className="admin-log-main">
                  <div className="admin-log-type mono">{event.event_type}</div>
                  {event.path && <div className="admin-log-path mono">{event.path}</div>}
                  {event.data && (
                    <div className="admin-log-data">
                      <pre>{JSON.stringify(event.data, null, 2)}</pre>
                    </div>
                  )}
                  {jumpUrl && (
                    <button
                      type="button"
                      className="btn btn-outline"
                      onClick={() => window.open(jumpUrl, '_blank', 'noopener,noreferrer')}
                    >
                      Open Map at this view
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        !isLoading && <div className="admin-muted">No events.</div>
      )}
    </div>
  );
}

export function AdminPage() {
  const [token, setToken] = useState<string>(() => {
    try {
      return (sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) ?? '').trim();
    } catch {
      return '';
    }
  });

  useEffect(() => {
    try {
      if (token) sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token);
      else sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
    } catch {
      // ignore
    }
  }, [token]);

  const value = useMemo<AdminAuth>(() => ({ token, setToken }), [token]);

  return (
    <AdminAuthContext.Provider value={value}>
      <div className="admin-page">
        <AdminHeader />
        <Routes>
          <Route index element={<IpListView />} />
          <Route path="ip/:ip" element={<IpDetailView />} />
          <Route path="instance/:instanceId" element={<InstanceDetailView />} />
          <Route path="instance/:instanceId/log" element={<InstanceLogView />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </div>
    </AdminAuthContext.Provider>
  );
}
