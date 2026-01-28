import { describe, it, expect, vi, beforeEach } from 'vitest';
import api from '../../services/api';

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get: vi.fn(),
      post: vi.fn(),
      delete: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    })),
  },
}));

describe('API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('regions', () => {
    it('has listRegions method', () => {
      expect(typeof api.listRegions).toBe('function');
    });

    it('has getRegion method', () => {
      expect(typeof api.getRegion).toBe('function');
    });

    it('has createRegion method', () => {
      expect(typeof api.createRegion).toBe('function');
    });
  });

  describe('metrics', () => {
    it('has getMetrics method', () => {
      expect(typeof api.getMetrics).toBe('function');
    });

    it('has comparePeriods method', () => {
      expect(typeof api.comparePeriods).toBe('function');
    });
  });

  describe('exports', () => {
    it('has exportPdf method', () => {
      expect(typeof api.exportPdf).toBe('function');
    });

    it('has exportCsv method', () => {
      expect(typeof api.exportCsv).toBe('function');
    });

    it('has exportAnimation method', () => {
      expect(typeof api.exportAnimation).toBe('function');
    });

    it('has getExportDownloadUrl method', () => {
      expect(typeof api.getExportDownloadUrl).toBe('function');
    });
  });

  describe('tiles', () => {
    it('has getTileUrl function', () => {
      expect(typeof api.getTileUrl).toBe('function');
    });

    it('generates correct region tile URL (with and without date)', () => {
      const urlNoDate = api.getTileUrl('region-123', 'ndvi');
      expect(urlNoDate).toContain('region-123');
      expect(urlNoDate).toContain('ndvi');
      expect(urlNoDate).not.toContain('date=');

      const urlWithDate = api.getTileUrl('region-123', 'ndvi', '2024-01-15');
      expect(urlWithDate).toContain('region-123');
      expect(urlWithDate).toContain('ndvi');
      expect(urlWithDate).toContain('date=2024-01-15');
    });

    it('generates correct US tile URL', () => {
      const url = api.getUSTileUrl('nightlights', '2024-01');
      expect(url).toContain('tiles/us/nightlights/2024-01');
    });

    it('generates correct world tile URL', () => {
      const url = api.getWorldTileUrl('nightlights', '2024-01');
      expect(url).toContain('tiles/world/nightlights/2024-01');
    });
  });

  describe('date helpers', () => {
    it('converts dates to year-month', () => {
      expect(api.dateToYearMonth('2024-01-15')).toBe('2024-01');
    });

    it('chooses correct tile date string based on granularity/metric', () => {
      expect(api.getTileDateString('2024-01-15', 'nightlights', 'daily')).toBe('2024-01-15');
      expect(api.getTileDateString('2024-01-15', 'active_fire', 'daily')).toBe('2024-01-15');
      expect(api.getTileDateString('2024-01-15', 'ndvi', 'daily')).toBe('2024-01');
      expect(api.getTileDateString('2024-01-15', 'nightlights', 'monthly')).toBe('2024-01');
    });
  });
});
