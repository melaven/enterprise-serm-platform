/**
 * Demo Service - API wrapper с fallback на mock данные
 * Автоматически переключается на моки когда backend недоступен
 */

import * as realApi from './services';
import * as mockData from './mockData';

// Проверяем режим demo из environment variables
const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';

// ========================================
// Auth Services with Demo Fallback
// ========================================

export async function login(credentials: realApi.LoginRequest): Promise<realApi.AuthResponse> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay();
    console.log('[DEMO MODE] Mock login:', credentials.email);
    return mockData.MOCK_AUTH_RESPONSE;
  }

  try {
    return await realApi.login(credentials);
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    await mockData.simulateNetworkDelay();
    return mockData.MOCK_AUTH_RESPONSE;
  }
}

export async function register(userData: realApi.RegisterRequest): Promise<realApi.RegisterResponse> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay();
    console.log('[DEMO MODE] Mock register:', userData.email);
    return mockData.MOCK_USER;
  }

  try {
    return await realApi.register(userData);
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    await mockData.simulateNetworkDelay();
    return mockData.MOCK_USER;
  }
}

export async function getCurrentUser(): Promise<realApi.UserProfile> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay(200);
    return mockData.MOCK_USER;
  }

  try {
    return await realApi.getCurrentUser();
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    return mockData.MOCK_USER;
  }
}

export async function logout(): Promise<void> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay(200);
    console.log('[DEMO MODE] Mock logout');
    return;
  }

  try {
    await realApi.logout();
  } catch (error) {
    console.warn('[API Error] Ignoring logout error in demo mode:', error);
  }
}

export async function refreshToken(refresh_token: string): Promise<realApi.AuthResponse> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay();
    return mockData.MOCK_AUTH_RESPONSE;
  }

  try {
    return await realApi.refreshToken(refresh_token);
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    return mockData.MOCK_AUTH_RESPONSE;
  }
}

// ========================================
// Reviews Services with Demo Fallback
// ========================================

export async function getReviews(params?: {
  page?: number;
  page_size?: number;
  platform?: string;
  sentiment?: string;
  search?: string;
}): Promise<realApi.PaginatedResponse<realApi.Review>> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay();
    console.log('[DEMO MODE] Mock getReviews:', params);
    return mockData.getPaginatedReviews(params);
  }

  try {
    return await realApi.getReviews(params);
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    await mockData.simulateNetworkDelay();
    return mockData.getPaginatedReviews(params);
  }
}

export async function getReviewById(reviewId: string): Promise<realApi.Review> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay();
    const review = mockData.MOCK_REVIEWS.find((r) => r.id === reviewId);
    if (!review) {
      throw new Error(`Review ${reviewId} not found in demo data`);
    }
    return review;
  }

  try {
    return await realApi.getReviewById(reviewId);
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    const review = mockData.MOCK_REVIEWS.find((r) => r.id === reviewId);
    if (!review) {
      throw new Error(`Review ${reviewId} not found`);
    }
    return review;
  }
}

// ========================================
// Dashboard Services with Demo Fallback
// ========================================

export async function getDashboardSummary(): Promise<realApi.DashboardSummary> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay();
    console.log('[DEMO MODE] Mock dashboard summary');
    return mockData.MOCK_DASHBOARD_SUMMARY;
  }

  try {
    return await realApi.getDashboardSummary();
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    await mockData.simulateNetworkDelay();
    return mockData.MOCK_DASHBOARD_SUMMARY;
  }
}

// ========================================
// Parser Services with Demo Fallback
// ========================================

export async function startParserJob(jobRequest: realApi.ParserJobRequest): Promise<{ job_id: string }> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay(1000);
    const jobId = mockData.generateMockJobId();
    console.log('[DEMO MODE] Mock parser job started:', jobId);
    return { job_id: jobId };
  }

  try {
    return await realApi.startParserJob(jobRequest);
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    await mockData.simulateNetworkDelay(1000);
    const jobId = mockData.generateMockJobId();
    return { job_id: jobId };
  }
}

export async function getParserJobStatus(jobId: string): Promise<realApi.ParserJobResponse> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay(300);
    console.log('[DEMO MODE] Mock parser job status:', jobId);
    return {
      job_id: jobId,
      state: 'succeeded',
      result: {
        reviews_found: 12,
        reviews_new: 10,
        reviews_saved: 10,
        ai_enriched: 9,
        ai_pending: 1,
        duration_ms: 3450,
      },
      error: null,
    };
  }

  try {
    return await realApi.getParserJobStatus(jobId);
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    return {
      job_id: jobId,
      state: 'succeeded',
      result: {
        reviews_found: 12,
        reviews_new: 10,
        reviews_saved: 10,
        ai_enriched: 9,
        ai_pending: 1,
        duration_ms: 3450,
      },
      error: null,
    };
  }
}

// ========================================
// Demo Mode Utilities
// ========================================

/**
 * Проверка активности demo mode
 */
export function isDemoModeActive(): boolean {
  return isDemoMode;
}

/**
 * Получить mock quota для demo
 */
export function getMockQuota() {
  return mockData.MOCK_QUOTA;
}

// ========================================
// Quotas & Billing Services with Demo Fallback
// ========================================

export async function getQuotaStatus(): Promise<realApi.QuotaStatus> {
  if (isDemoMode) {
    await mockData.simulateNetworkDelay();
    console.log('[DEMO MODE] Mock quota status');
    return mockData.MOCK_QUOTA_STATUS;
  }

  try {
    return await realApi.getQuotaStatus();
  } catch (error) {
    console.warn('[API Error] Falling back to demo mode:', error);
    await mockData.simulateNetworkDelay();
    return mockData.MOCK_QUOTA_STATUS;
  }
}

export async function getSubscriptionTiers(): Promise<realApi.SubscriptionTier[]> {
  await mockData.simulateNetworkDelay();
  console.log('[DEMO MODE] Mock subscription tiers');
  return mockData.MOCK_SUBSCRIPTION_TIERS;
}

export async function getAPIKeys(): Promise<realApi.APIKey[]> {
  await mockData.simulateNetworkDelay();
  console.log('[DEMO MODE] Mock API keys');
  return mockData.MOCK_API_KEYS;
}

export async function revokeAPIKey(keyId: string): Promise<void> {
  await mockData.simulateNetworkDelay();
  console.log('[DEMO MODE] Mock revoke API key:', keyId);
}

/**
 * Логирование статуса demo mode
 */
if (isDemoMode) {
  console.log(
    '%c[DEMO MODE ACTIVE]',
    'background: #C5FF4A; color: #000; font-weight: bold; padding: 4px 8px;',
    'Все API запросы используют mock данные'
  );
}
