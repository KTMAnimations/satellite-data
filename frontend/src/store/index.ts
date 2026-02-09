import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Region, MetricType, DateRange, MapState, ExportResponse } from '../types';
import { ALL_METRIC_TYPES } from '../config/metrics';

export type NavSection = 'fullmap' | 'dashboard' | 'regions' | 'exports';
export type DaytimeBasemap = 'carto_light' | 'maptiler_osm';

const DAYTIME_BASEMAPS = new Set<DaytimeBasemap>(['carto_light', 'maptiler_osm']);

interface AppState {
  // Selected region
  selectedRegion: Region | null;
  setSelectedRegion: (region: Region | null) => void;

  // Map state
  mapState: MapState;
  updateMapState: (patch: Partial<MapState>) => void;

  // Date range
  dateRange: DateRange;
  setDateRange: (range: DateRange) => void;

  // Selected metrics
  selectedMetrics: MetricType[];
  toggleMetric: (metric: MetricType) => void;
  setSelectedMetrics: (metrics: MetricType[]) => void;

  // Comparison mode
  comparisonMode: boolean;
  setComparisonMode: (enabled: boolean) => void;
  comparisonPeriodA: DateRange | null;
  comparisonPeriodB: DateRange | null;
  setComparisonPeriodA: (range: DateRange | null) => void;
  setComparisonPeriodB: (range: DateRange | null) => void;

  // UI state
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  navLastPath: Record<NavSection, string>;
  setNavLastPath: (section: NavSection, path: string) => void;
  daytimeBasemap: DaytimeBasemap;
  setDaytimeBasemap: (basemap: DaytimeBasemap) => void;

  // Export queue (in-memory; not persisted)
  exportQueue: ExportResponse[];
  addExportToQueue: (exportItem: ExportResponse) => void;
  setExportQueue: (exports: ExportResponse[]) => void;
  clearExportQueue: () => void;
}

// Default to last 2 years of data for meaningful analysis
const defaultDateRange: DateRange = (() => {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(end.getFullYear() - 2);
  return { start, end };
})();

const DEFAULT_SELECTED_METRICS: MetricType[] = ['nightlights', 'ndvi'];
const METRIC_TYPE_SET = new Set<MetricType>(ALL_METRIC_TYPES);

function sanitizeSelectedMetrics(
  metrics: unknown,
  { fallbackWhenEmpty = false }: { fallbackWhenEmpty?: boolean } = {}
): MetricType[] {
  const candidates = Array.isArray(metrics) ? metrics : [];
  const filtered = candidates.filter(
    (metric): metric is MetricType => typeof metric === 'string' && METRIC_TYPE_SET.has(metric as MetricType)
  );

  if (filtered.length > 0) return filtered;
  return fallbackWhenEmpty ? [...DEFAULT_SELECTED_METRICS] : [];
}

function sanitizeDaytimeBasemap(value: unknown): DaytimeBasemap {
  if (typeof value === 'string' && DAYTIME_BASEMAPS.has(value as DaytimeBasemap)) {
    return value as DaytimeBasemap;
  }
  return 'carto_light';
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Selected region
      selectedRegion: null,
      setSelectedRegion: (region) => set({ selectedRegion: region }),

      // Map state
      mapState: {
        center: [27.5, -98.5795], // Slightly higher so the US-Mexico border stays visible
        zoom: 4,
        contextRegionId: null,
      },
      updateMapState: (patch) =>
        set((state) => ({ mapState: { ...state.mapState, ...patch } })),

      // Date range
      dateRange: defaultDateRange,
      setDateRange: (range) => set({ dateRange: range }),

      // Selected metrics
      selectedMetrics: [...DEFAULT_SELECTED_METRICS],
      toggleMetric: (metric) =>
        set((state) => ({
          selectedMetrics: state.selectedMetrics.includes(metric)
            ? state.selectedMetrics.filter((m) => m !== metric)
            : [...state.selectedMetrics, metric],
        })),
      setSelectedMetrics: (metrics) =>
        set({ selectedMetrics: sanitizeSelectedMetrics(metrics, { fallbackWhenEmpty: false }) }),

      // Comparison mode
      comparisonMode: false,
      setComparisonMode: (enabled) => set({ comparisonMode: enabled }),
      comparisonPeriodA: null,
      comparisonPeriodB: null,
      setComparisonPeriodA: (range) => set({ comparisonPeriodA: range }),
      setComparisonPeriodB: (range) => set({ comparisonPeriodB: range }),

      // UI state
      // Closed by default (especially important on mobile where the nav is an overlay).
      sidebarOpen: false,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      navLastPath: {
        fullmap: '/map',
        dashboard: '/dashboard',
        regions: '/regions',
        exports: '/exports',
      },
      setNavLastPath: (section, path) =>
        set((state) => ({ navLastPath: { ...state.navLastPath, [section]: path } })),
      daytimeBasemap: 'carto_light',
      setDaytimeBasemap: (basemap) => set({ daytimeBasemap: sanitizeDaytimeBasemap(basemap) }),

      // Export queue (in-memory; not persisted)
      exportQueue: [],
      addExportToQueue: (exportItem) =>
        set((state) => ({ exportQueue: [exportItem, ...state.exportQueue] })),
      setExportQueue: (exports) => set({ exportQueue: exports }),
      clearExportQueue: () => set({ exportQueue: [] }),
    }),
    {
      name: 'satellite-migration-storage',
      partialize: (state) => ({
        selectedMetrics: state.selectedMetrics,
        daytimeBasemap: state.daytimeBasemap,
      }),
      merge: (persistedState, currentState) => {
        const persisted = (persistedState ?? {}) as Partial<AppState>;
        return {
          ...currentState,
          selectedMetrics: sanitizeSelectedMetrics(persisted.selectedMetrics, { fallbackWhenEmpty: true }),
          daytimeBasemap: sanitizeDaytimeBasemap(persisted.daytimeBasemap),
        };
      },
    }
  )
);
