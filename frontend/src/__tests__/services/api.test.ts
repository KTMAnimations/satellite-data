import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
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

    it('generates correct tile URL', () => {
      const url = api.getTileUrl('ndvi', '2024-01');
      expect(url).toContain('ndvi');
      expect(url).toContain('2024-01');
    });
  });

  describe('granularity mapping', () => {
    it('has getMetricGranularity function', () => {
      expect(typeof api.getMetricGranularity).toBe('function');
    });

    it('returns correct granularity for different metrics', () => {
      expect(api.getMetricGranularity('nightlights')).toBe('monthly');
      expect(api.getMetricGranularity('ndvi')).toBe('weekly');
      expect(api.getMetricGranularity('urban_density')).toBe('yearly');
    });
  });
});
