/**
 * Mock Data Service для Demo Mode
 * Используется когда backend недоступен или VITE_DEMO_MODE=true
 */

import type { Review, DashboardSummary, AuthResponse, UserProfile, PaginatedResponse } from './services';
import demoReviewDump from '../mocks/reviews_mock.json';

function mapModerationStatus(
  status: string,
): NonNullable<Review['moderation_status']> {
  switch (status) {
    case 'new':
    case 'drafted':
    case 'pending_moderation':
    case 'published':
      return status;
    default:
      throw new Error(`Unsupported review moderation status: ${status}`);
  }
}

// ========================================
// Mock Users
// ========================================

export const MOCK_USER: UserProfile = {
  id: 'demo-user-001',
  email: 'demo@tenable-serm.com',
  tenant_id: 'demo-tenant-001',
  created_at: '2026-01-01T00:00:00Z',
};

export const MOCK_AUTH_RESPONSE: AuthResponse = {
  access_token: 'demo_token_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
  token_type: 'bearer',
  expires_in: 3600,
  refresh_token: 'demo_refresh_token',
  user: {
    id: MOCK_USER.id,
    email: MOCK_USER.email,
    tenant_id: MOCK_USER.tenant_id ?? 'demo-tenant-001',
  },
};

// ========================================
// Mock Reviews
// ========================================

export const MOCK_REVIEWS: Review[] = demoReviewDump.map((review) => {
  const sentiment =
    review.sentiment === 'positive'
      ? 'POSITIVE'
      : review.sentiment === 'negative'
        ? 'NEGATIVE'
        : 'NEUTRAL';

  return {
    id: review.id,
    branch_id: review.branch_id,
    author_name: review.author_name,
    platform: review.platform,
    rating: review.rating,
    text: review.text,
    sentiment,
    threat_level: review.rating <= 2 ? 6 - review.rating : null,
    suggested_reply: null,
    status: review.rating <= 2 ? 'new' : 'resolved',
    moderation_status: mapModerationStatus(review.moderation_status),
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: review.rating <= 2,
    created_at: review.created_at,
  };
});

// ========================================
// Mock Dashboard Summary
// ========================================

export const MOCK_DASHBOARD_SUMMARY: DashboardSummary = {
  total_reviews: MOCK_REVIEWS.length,
  sentiment: {
    positive: MOCK_REVIEWS.filter((review) => review.sentiment === 'POSITIVE').length,
    neutral: MOCK_REVIEWS.filter((review) => review.sentiment === 'NEUTRAL').length,
    negative: MOCK_REVIEWS.filter((review) => review.sentiment === 'NEGATIVE').length,
    unclassified: 0,
    total: MOCK_REVIEWS.length,
  },
  timeline: [...new Set(MOCK_REVIEWS.map((review) => review.created_at.slice(0, 10)))]
    .sort()
    .map((date) => ({
      date,
      reviews: MOCK_REVIEWS.filter((review) => review.created_at.startsWith(date)).length,
    })),
  critical_reviews: MOCK_REVIEWS.filter((review) => review.is_critical).length,
  ai_pending: MOCK_REVIEWS.filter((review) => review.ai_pending).length,
};

// ========================================
// Mock API Response Helpers
// ========================================

/**
 * Симулирует задержку сети (300-800ms)
 */
export const simulateNetworkDelay = (ms?: number): Promise<void> => {
  const delay = ms ?? Math.random() * 500 + 300;
  return new Promise((resolve) => setTimeout(resolve, delay));
};

/**
 * Фильтрация и пагинация отзывов
 */
export const getPaginatedReviews = (params?: {
  page?: number;
  page_size?: number;
  platform?: string;
  sentiment?: string;
  search?: string;
}): PaginatedResponse<Review> => {
  let filtered = [...MOCK_REVIEWS];

  if (params?.platform) {
    filtered = filtered.filter((r) => r.platform?.toLowerCase().includes(params.platform!.toLowerCase()));
  }

  if (params?.sentiment) {
    filtered = filtered.filter((r) => r.sentiment === params.sentiment);
  }

  if (params?.search) {
    const search = params.search.toLowerCase();
    filtered = filtered.filter(
      (review) =>
        review.text.toLowerCase().includes(search) ||
        review.tags.some((tag) => tag.toLowerCase().includes(search)),
    );
  }

  const page = params?.page ?? 1;
  const page_size = params?.page_size ?? 20;
  const startIndex = (page - 1) * page_size;
  const endIndex = startIndex + page_size;

  const items = filtered.slice(startIndex, endIndex);
  const total = filtered.length;
  const total_pages = Math.ceil(total / page_size);

  return {
    items,
    total,
    page,
    page_size,
    total_pages,
  };
};

/**
 * Генерация случайного Job ID для парсера
 */
export const generateMockJobId = (): string => {
  return `demo-job-${Date.now()}-${Math.random().toString(36).substring(7)}`;
};

// ========================================
// Mock Quota Data
// ========================================

export const MOCK_QUOTA = {
  llmTokens: {
    used: 125430,
    limit: 500000,
  },
  reviewsParsed: {
    used: 8234,
    limit: 10000,
  },
  resetDate: '2026-12-31',
};

// ========================================
// Mock Quota Status (Full API Schema)
// ========================================

import type { QuotaStatus, SubscriptionTier, APIKey } from './services';

export const MOCK_QUOTA_STATUS: QuotaStatus = {
  tenant_id: 'demo-tenant-001',
  limits: {
    max_llm_tokens: 500000,
    max_reviews: 10000,
  },
  usage: {
    used_llm_tokens: 125430,
    used_reviews: 8234,
    reserved_llm_tokens: 2500,
  },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-10-13T12:30:00Z',
  total_tokens_committed: 127930,
  tokens_available: 372070,
  reviews_available: 1766,
  tokens_usage_percent: 25.59,
  reviews_usage_percent: 82.34,
};

export const MOCK_SUBSCRIPTION_TIERS: SubscriptionTier[] = [
  {
    id: 'starter',
    name: 'Starter',
    price: 49,
    currency: 'USD',
    interval: 'month',
    limits: {
      max_llm_tokens: 100000,
      max_reviews: 1000,
    },
    features: [
      '100K токенов для SI-анализа / месяц',
      '1,000 отзывов / месяц',
      'Базовая аналитика',
      'Email поддержка',
      '1 пользователь',
    ],
  },
  {
    id: 'pro',
    name: 'Professional',
    price: 149,
    currency: 'USD',
    interval: 'month',
    limits: {
      max_llm_tokens: 500000,
      max_reviews: 10000,
    },
    features: [
      '500K токенов для SI-анализа / месяц',
      '10,000 отзывов / месяц',
      'Расширенная аналитика',
      'Priority поддержка',
      'До 5 пользователей',
      'API доступ',
    ],
    recommended: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 499,
    currency: 'USD',
    interval: 'month',
    limits: {
      max_llm_tokens: 2000000,
      max_reviews: 50000,
    },
    features: [
      '2M токенов для SI-анализа / месяц',
      '50,000 отзывов / месяц',
      'Кастомная аналитика',
      'Dedicated менеджер',
      'Неограниченно пользователей',
      'API доступ + Webhooks',
      'SLA 99.9%',
    ],
  },
];

export const MOCK_API_KEYS: APIKey[] = [
  {
    id: 'key_001',
    name: 'Production Key',
    key_prefix: 'sk_prod_****...a8f2',
    created_at: '2026-09-01T10:00:00Z',
    last_used_at: '2026-10-13T08:45:00Z',
  },
  {
    id: 'key_002',
    name: 'Development Key',
    key_prefix: 'sk_dev_****...b3e9',
    created_at: '2026-09-15T14:30:00Z',
    last_used_at: '2026-10-12T16:20:00Z',
  },
  {
    id: 'key_003',
    name: 'Testing Key',
    key_prefix: 'sk_test_****...c7d4',
    created_at: '2026-10-01T09:15:00Z',
    last_used_at: null,
  },
];
