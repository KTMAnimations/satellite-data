import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Region, MetricType, DateRange, MapState } from '../types';

interface AppState {
  // Selected region
  selectedRegion: Region | null;
  setSelectedRegion: (region: Region | null) => void;

  // Map state
  mapState: MapState;
  setMapCenter: (center: [number, number]) => void;
  setMapZoom: (zoom: number) => void;

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

  // API key
  apiKey: string | null;
  setApiKey: (key: string | null) => void;
}

// Default to last 2 years of data for meaningful analysis
const defaultDateRange: DateRange = {
  start: new Date(2023, 0, 1),   // Jan 1, 2023
  end: new Date(),               // Today
};

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
        selectedRegionId: null,
      },
      setMapCenter: (center) =>
        set((state) => ({ mapState: { ...state.mapState, center } })),
      setMapZoom: (zoom) =>
        set((state) => ({ mapState: { ...state.mapState, zoom } })),

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

      // API key
      apiKey: null,
      setApiKey: (key) => set({ apiKey: key }),
    }),
    {
      name: 'satellite-migration-storage',
      partialize: (state) => ({
        apiKey: state.apiKey,
        selectedMetrics: state.selectedMetrics,
      }),
    }
  )
);
