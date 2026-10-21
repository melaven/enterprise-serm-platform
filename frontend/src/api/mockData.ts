/**
 * Mock Data Service для Demo Mode
 * Используется когда backend недоступен или VITE_DEMO_MODE=true
 */

import type { Review, DashboardSummary, AuthResponse, UserProfile, PaginatedResponse } from './services';

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

export const MOCK_REVIEWS: Review[] = [
  {
    id: '1',
    platform: '2GIS',
    rating: 5,
    text: 'Положительный отзыв; оценка 5/5.',
    sentiment: 'POSITIVE',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-10T14:35:00Z',
  },
  {
    id: '2',
    platform: '2GIS',
    rating: 4,
    text: 'Положительный отзыв; оценка 4/5.',
    sentiment: 'POSITIVE',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-09T11:20:00Z',
  },
  {
    id: '3',
    platform: '2GIS',
    rating: 2,
    text: 'Негативный отзыв; оценка 2/5.',
    sentiment: 'NEGATIVE',
    threat_level: 4,
    suggested_reply: null,
    status: 'new',
    tags: ['PRODUCT_QUALITY'],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: true,
    created_at: '2026-10-08T16:50:00Z',
  },
  {
    id: '4',
    platform: 'Yandex Maps',
    rating: 5,
    text: 'Положительный отзыв; оценка 5/5.',
    sentiment: 'POSITIVE',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-07T09:25:00Z',
  },
  {
    id: '5',
    platform: 'Google Reviews',
    rating: 3,
    text: 'Нейтральный отзыв; оценка 3/5.',
    sentiment: 'NEUTRAL',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-06T13:15:00Z',
  },
  {
    id: '6',
    platform: '2GIS',
    rating: 5,
    text: 'Положительный отзыв; оценка 5/5.',
    sentiment: 'POSITIVE',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-05T10:35:00Z',
  },
  {
    id: '7',
    platform: 'Yandex Maps',
    rating: 1,
    text: 'Негативный отзыв; оценка 1/5.',
    sentiment: 'NEGATIVE',
    threat_level: 5,
    suggested_reply: null,
    status: 'new',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: true,
    created_at: '2026-10-04T15:05:00Z',
  },
  {
    id: '8',
    platform: 'Google Reviews',
    rating: 4,
    text: 'Положительный отзыв; оценка 4/5.',
    sentiment: 'POSITIVE',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-03T12:25:00Z',
  },
  {
    id: '9',
    platform: '2GIS',
    rating: 3,
    text: 'Нейтральный отзыв; оценка 3/5.',
    sentiment: 'NEUTRAL',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-02T14:45:00Z',
  },
  {
    id: '10',
    platform: 'Yandex Maps',
    rating: 5,
    text: 'Положительный отзыв; оценка 5/5.',
    sentiment: 'POSITIVE',
    threat_level: null,
    suggested_reply: null,
    status: 'resolved',
    tags: [],
    financial_impact: 0,
    si_response: null,
    auto_reply: null,
    ai_pending: false,
    is_critical: false,
    created_at: '2026-10-01T11:05:00Z',
  },
];

// ========================================
// Mock Dashboard Summary
// ========================================

export const MOCK_DASHBOARD_SUMMARY: DashboardSummary = {
  total_reviews: MOCK_REVIEWS.length,
  sentiment: {
    positive: 6,
    neutral: 2,
    negative: 2,
    unclassified: 0,
    total: 10,
  },
  timeline: [
    { date: '2026-10-01', reviews: 1 },
    { date: '2026-10-02', reviews: 1 },
    { date: '2026-10-03', reviews: 1 },
    { date: '2026-10-04', reviews: 1 },
    { date: '2026-10-05', reviews: 1 },
    { date: '2026-10-06', reviews: 1 },
    { date: '2026-10-07', reviews: 1 },
    { date: '2026-10-08', reviews: 1 },
    { date: '2026-10-09', reviews: 1 },
    { date: '2026-10-10', reviews: 1 },
  ],
  critical_reviews: 2,
  ai_pending: 0,
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
