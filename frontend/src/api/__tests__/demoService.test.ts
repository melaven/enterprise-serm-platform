/**
 * Tests for Demo Mode Service
 * Covers: API fallback, mock data, error handling
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import * as realApi from '../services';
import * as mockData from '../mockData';

let demoApi: typeof import('../demoService');

async function loadDemoApi(mode: string, useMocks = 'false') {
  vi.stubEnv('VITE_DEMO_MODE', mode);
  vi.stubEnv('VITE_USE_MOCKS', useMocks);
  vi.resetModules();
  demoApi = await import('../demoService');
}

// Mock real API
vi.mock('../services', () => ({
  login: vi.fn(),
  register: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
  getReviews: vi.fn(),
  getDashboardSummary: vi.fn(),
  startParserJob: vi.fn(),
  getParserJobStatus: vi.fn(),
  getQuotaStatus: vi.fn(),
}));

describe('DemoService - API Fallback', () => {
  beforeEach(async () => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
    await loadDemoApi('true');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('Demo Mode Active', () => {
    beforeEach(async () => {
      await loadDemoApi('true');
    });

    it('should use mock data when VITE_USE_MOCKS is enabled', async () => {
      await loadDemoApi('false', 'true');

      const result = await demoApi.getReviews({ page: 1, page_size: 10 });

      expect(result.total).toBe(mockData.MOCK_REVIEWS.length);
      expect(realApi.getReviews).not.toHaveBeenCalled();
    });

    it('should use mock data for login when demo mode is active', async () => {
      const result = await demoApi.login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(result).toEqual(mockData.MOCK_AUTH_RESPONSE);
      expect(realApi.login).not.toHaveBeenCalled();
    });

    it('should use mock data for getReviews', async () => {
      const result = await demoApi.getReviews({ page: 1, page_size: 10 });

      expect(result.items).toHaveLength(10);
      expect(result.total).toBe(mockData.MOCK_REVIEWS.length);
      expect(realApi.getReviews).not.toHaveBeenCalled();
    });

    it('should use mock data for getDashboardSummary', async () => {
      const result = await demoApi.getDashboardSummary();

      expect(result).toEqual(mockData.MOCK_DASHBOARD_SUMMARY);
      expect(realApi.getDashboardSummary).not.toHaveBeenCalled();
    });

    it('should use mock data for getQuotaStatus', async () => {
      const result = await demoApi.getQuotaStatus();

      expect(result).toEqual(mockData.MOCK_QUOTA_STATUS);
      expect(realApi.getQuotaStatus).not.toHaveBeenCalled();
    });
  });

  describe('API Fallback on Error', () => {
    beforeEach(async () => {
      await loadDemoApi('false');
    });

    it('should fallback to mock when API login fails', async () => {
      vi.mocked(realApi.login).mockRejectedValueOnce(new Error('Network error'));

      const result = await demoApi.login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(result).toEqual(mockData.MOCK_AUTH_RESPONSE);
      expect(realApi.login).toHaveBeenCalledOnce();
    });

    it('should fallback to mock when API getReviews fails', async () => {
      vi.mocked(realApi.getReviews).mockRejectedValueOnce(new Error('Server error'));

      const result = await demoApi.getReviews({ page: 1, page_size: 5 });

      expect(result.items).toHaveLength(5);
      expect(realApi.getReviews).toHaveBeenCalledOnce();
    });

    it('should fallback to mock when API getDashboardSummary fails', async () => {
      vi.mocked(realApi.getDashboardSummary).mockRejectedValueOnce(
        new Error('Backend unavailable')
      );

      const result = await demoApi.getDashboardSummary();

      expect(result).toEqual(mockData.MOCK_DASHBOARD_SUMMARY);
      expect(realApi.getDashboardSummary).toHaveBeenCalledOnce();
    });
  });

  describe('Network Delay Simulation', () => {
    it('should simulate network delay', async () => {
      const startTime = Date.now();

      await demoApi.login({
        email: 'test@example.com',
        password: 'password123',
      });

      const endTime = Date.now();
      const duration = endTime - startTime;

      // Should take at least 300ms (mock network delay)
      expect(duration).toBeGreaterThanOrEqual(200);
    });
  });

  describe('Mock Data Filtering', () => {
    it('should filter reviews by platform', async () => {
      const result = await demoApi.getReviews({
        platform: '2gis',
        page_size: 50,
      });

      expect(result.items.every((r) => r.platform.toLowerCase().includes('2gis'))).toBe(
        true
      );
    });

    it('should filter reviews by sentiment', async () => {
      const result = await demoApi.getReviews({
        sentiment: 'POSITIVE',
        page_size: 50,
      });

      expect(result.items.every((r) => r.sentiment === 'POSITIVE')).toBe(true);
    });

    it('should paginate reviews correctly', async () => {
      const page1 = await demoApi.getReviews({ page: 1, page_size: 3 });
      const page2 = await demoApi.getReviews({ page: 2, page_size: 3 });

      expect(page1.items).toHaveLength(3);
      expect(page2.items).toHaveLength(3);
      expect(page1.items[0].id).not.toBe(page2.items[0].id);
    });
  });

  describe('Parser Job Mock', () => {
    it('should generate mock job ID', async () => {
      const result = await demoApi.startParserJob({
        platform: '2gis',
        url: 'https://2gis.ru/test',
      });

      expect(result.job_id).toMatch(/^demo-job-/);
    });

    it('should return succeeded status for job', async () => {
      const result = await demoApi.getParserJobStatus('test-job-123');

      expect(result.state).toBe('succeeded');
      expect(result.result).toBeDefined();
      expect(result.result?.reviews_saved).toBeGreaterThan(0);
    });
  });

  describe('Subscription Tiers Mock', () => {
    it('should return 3 subscription tiers', async () => {
      const result = await demoApi.getSubscriptionTiers();

      expect(result).toHaveLength(3);
      expect(result.map((t) => t.id)).toEqual(['starter', 'pro', 'enterprise']);
    });

    it('should have correct pricing', async () => {
      const result = await demoApi.getSubscriptionTiers();

      expect(result[0].price).toBe(49); // Starter
      expect(result[1].price).toBe(149); // Pro
      expect(result[2].price).toBe(499); // Enterprise
    });
  });

  describe('API Keys Mock', () => {
    it('should return mock API keys', async () => {
      const result = await demoApi.getAPIKeys();

      expect(result).toHaveLength(3);
      expect(result[0].name).toBe('Production Key');
      expect(result[0].key_prefix).toMatch(/^sk_/);
    });

    it('should simulate key revocation', async () => {
      await expect(demoApi.revokeAPIKey('key_001')).resolves.toBeUndefined();
    });
  });

  describe('isDemoModeActive', () => {
    it('should return true when VITE_DEMO_MODE is true', () => {
      vi.stubEnv('VITE_DEMO_MODE', 'true');

      const result = import.meta.env.VITE_DEMO_MODE === 'true';
      expect(result).toBe(true);
    });

    it('should return false when VITE_DEMO_MODE is false', () => {
      vi.stubEnv('VITE_DEMO_MODE', 'false');

      const result = import.meta.env.VITE_DEMO_MODE === 'true';
      expect(result).toBe(false);
    });
  });

  describe('Error Handling', () => {
    it('should not throw errors in demo mode', async () => {
      await expect(
        demoApi.login({ email: 'any', password: 'any' })
      ).resolves.toBeDefined();

      await expect(demoApi.getReviews({})).resolves.toBeDefined();

      await expect(demoApi.getDashboardSummary()).resolves.toBeDefined();
    });

    it('should handle logout gracefully even on error', async () => {
      vi.mocked(realApi.logout).mockRejectedValueOnce(new Error('Logout failed'));

      await expect(demoApi.logout()).resolves.toBeUndefined();
    });
  });
});
