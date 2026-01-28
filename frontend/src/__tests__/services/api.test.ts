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
    it('has getTileTemplate method', () => {
      expect(typeof api.getTileTemplate).toBe('function');
    });
  });
});
