import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Region, MetricType, DateRange, MapState, ExportResponse } from '../types';

export type NavSection = 'dashboard' | 'regions' | 'animations' | 'exports' | 'gallery';

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
  activeTab: 'regions' | 'analysis' | 'exports' | 'gallery';
  setActiveTab: (tab: 'regions' | 'analysis' | 'exports' | 'gallery') => void;
  navLastPath: Record<NavSection, string>;
  setNavLastPath: (section: NavSection, path: string) => void;

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

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Selected region
      selectedRegion: null,
      setSelectedRegion: (region) => set({ selectedRegion: region }),

      // Map state
      mapState: {
        center: [39.8283, -98.5795], // Center of US
        zoom: 4,
        contextRegionId: null,
      },
      updateMapState: (patch) =>
        set((state) => ({ mapState: { ...state.mapState, ...patch } })),

      // Date range
      dateRange: defaultDateRange,
      setDateRange: (range) => set({ dateRange: range }),

      // Selected metrics
      selectedMetrics: ['nightlights', 'ndvi'],
      toggleMetric: (metric) =>
        set((state) => ({
          selectedMetrics: state.selectedMetrics.includes(metric)
            ? state.selectedMetrics.filter((m) => m !== metric)
            : [...state.selectedMetrics, metric],
        })),
      setSelectedMetrics: (metrics) => set({ selectedMetrics: metrics }),

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
      activeTab: 'regions',
      setActiveTab: (tab) => set({ activeTab: tab }),
      navLastPath: {
        dashboard: '/',
        regions: '/regions',
        animations: '/animations',
        exports: '/exports',
        gallery: '/gallery',
      },
      setNavLastPath: (section, path) =>
        set((state) => ({ navLastPath: { ...state.navLastPath, [section]: path } })),

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
      }),
    }
  )
);
