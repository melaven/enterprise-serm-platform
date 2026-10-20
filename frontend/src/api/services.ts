/**
 * Централизованный слой API сервисов
 * Все взаимодействия с backend происходят через эти функции
 */

import { createApiClient } from './client';
import { TokenStore } from './token';

// Создание API client с tokens и interceptors
const tokens = new TokenStore(typeof localStorage === 'undefined' ? null : localStorage);

export const apiClient = createApiClient({
  baseURL: '/api',
  tokens,
  onUnauthorized: () => {
    // Redirect to login on 401
    window.location.href = '/login';
  },
});

// Экспортируем tokens для использования в других местах
export { tokens };

// ============================================================
// ТИПЫ
// ============================================================

// Обертка ответа API с пагинацией
export interface ApiResponse<T> {
  success: boolean;
  data: T;
}

// Обертка для пагинированных данных
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Review {
  id: string;
  external_review_id: string | null;
  platform: string | null;
  author_name: string;
  rating: number;
  text: string;
  sentiment: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | 'UNCLASSIFIED' | null;
  threat_level: number | null;
  suggested_reply: string | null;
  tags: string[];
  status: 'new' | 'si_processing' | 'resolved' | 'lost';
  financial_impact: number;
  si_response: string | null;
  auto_reply: string | null;
  ai_pending: boolean;
  is_critical: boolean;
  created_at: string;
}

export interface ApproveAiResponseResult {
  review_id: string;
  status: Review['status'];
  ai_pending: boolean;
}

export interface PublishReviewReplyResult {
  review_id: string;
  status: 'queued';
  job_id: string;
}

export interface GoogleBusinessIntegration {
  platform: 'google_business';
  external_account_id: string;
  external_location_id: string;
  is_active: boolean;
}

export interface DashboardSummary {
  total_reviews: number;
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
    unclassified: number;
    total: number;
  };
  timeline: Array<{
    date: string;
    reviews: number;
  }>;
  critical_reviews: number;
  ai_pending: number;
}

export type DashboardSummaryResponse = ApiResponse<DashboardSummary>;

export interface ParserJobRequest {
  platform: string;
  url: string;
}

export interface ParserJobResult {
  reviews_found: number;
  reviews_new: number;
  reviews_saved: number;
  ai_enriched: number;
  ai_pending: number;
  duration_ms: number;
}

export interface ParserJobResponse {
  job_id: string;
  state: 'queued' | 'in_progress' | 'succeeded' | 'failed';
  result: ParserJobResult | null;
  error: string | null;
}

export interface QuotaLimits {
  max_llm_tokens: number;
  max_reviews: number;
}

export interface QuotaUsage {
  used_llm_tokens: number;
  used_reviews: number;
  reserved_llm_tokens: number;
}

export interface QuotaStatus {
  tenant_id: string;
  limits: QuotaLimits;
  usage: QuotaUsage;
  created_at: string;
  updated_at: string;
  // Computed properties
  total_tokens_committed?: number;
  tokens_available?: number;
  reviews_available?: number;
  tokens_usage_percent?: number;
  reviews_usage_percent?: number;
}

export interface SubscriptionTier {
  id: 'starter' | 'pro' | 'enterprise';
  name: string;
  price: number;
  currency: string;
  interval: 'month' | 'year';
  limits: QuotaLimits;
  features: string[];
  recommended?: boolean;
}

export interface APIKey {
  id: string;
  name: string;
  key_prefix: string; // "sk_live_****..."
  created_at: string;
  last_used_at: string | null;
}

export interface CreateAPIKeyRequest {
  name: string;
}

export interface CreateAPIKeyResponse {
  id: string;
  name: string;
  key: string; // Full key shown ONLY once
  key_prefix: string;
  created_at: string;
}

export interface Webhook {
  id: string;
  url: string;
  secret_key_prefix: string; // "whsec_****..."
  events: string[];
  active: boolean;
  created_at: string;
  last_triggered_at: string | null;
}

export interface CreateWebhookRequest {
  url: string;
  events?: string[];
}

export interface CreateWebhookResponse {
  id: string;
  url: string;
  secret_key: string; // Full secret shown ONLY once
  secret_key_prefix: string;
  events: string[];
  active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
  tenant_id?: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  refresh_token: string;
  user: {
    id: string;
    email: string;
    tenant_id: string;
  };
}

export interface UserProfile {
  id: string;
  email: string;
  tenant_id?: string;
  created_at: string;
}

// ============================================================
// AUTH SERVICES
// ============================================================

/**
 * Вход пользователя
 */
export async function login(credentials: LoginRequest): Promise<AuthResponse> {
  const params = new URLSearchParams();
  params.append('username', credentials.email);
  params.append('password', credentials.password);

  const { data } = await apiClient.post<AuthResponse>('/v1/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  });
  return data;
}

/**
 * Регистрация нового пользователя
 * tenant_id больше не отправляется с клиента
 */
export async function register(userData: RegisterRequest): Promise<RegisterResponse> {
  const { data } = await apiClient.post<RegisterResponse>('/v1/auth/register', userData);
  return data;
}

/**
 * Получение профиля текущего пользователя
 */
export async function getCurrentUser(): Promise<UserProfile> {
  const { data } = await apiClient.get<UserProfile>('/v1/auth/me');
  return data;
}

/**
 * Выход из системы
 */
export async function logout(): Promise<void> {
  await apiClient.post('/v1/auth/logout');
}

/**
 * Обновление access token через refresh token
 */
export async function refreshToken(refresh_token: string): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>('/v1/auth/refresh', { refresh_token });
  return data;
}

// ============================================================
// REVIEWS SERVICES
// ============================================================

/**
 * Получение списка отзывов с пагинацией
 * Ответ обернут в { success: true, data: { items: [...], total, page, page_size, total_pages } }
 */
export async function getReviews(params?: {
  page?: number;
  page_size?: number;
  platform?: string;
  sentiment?: string;
  search?: string;
}): Promise<PaginatedResponse<Review>> {
  const { data } = await apiClient.get<ApiResponse<PaginatedResponse<Review>>>('/v1/reviews', { params });
  return data.data;
}

/**
 * Подтвердить AI-ответ отзыва текущего tenant.
 */
export async function approveAiResponse(
  reviewId: string,
): Promise<ApproveAiResponseResult> {
  const { data } = await apiClient.post<ApiResponse<ApproveAiResponseResult>>(
    `/v1/reviews/${reviewId}/approve-ai-response`,
  );
  return data.data;
}

/**
 * Queue publication of an edited or generated reply to the review platform.
 */
export async function publishReviewReply(
  reviewId: string,
  replyText: string,
): Promise<PublishReviewReplyResult> {
  const { data } = await apiClient.post<PublishReviewReplyResult>(
    `/v1/reviews/${encodeURIComponent(reviewId)}/reply`,
    { reply_text: replyText },
  );
  return data;
}

export async function configureGoogleBusinessIntegration(input: {
  access_token: string;
  external_account_id: string;
  external_location_id: string;
}): Promise<GoogleBusinessIntegration> {
  const { data } = await apiClient.put<GoogleBusinessIntegration>(
    '/v1/platforms/integrations/google-business',
    input,
  );
  return data;
}

/**
 * Получение отзыва по ID
 */
export async function getReviewById(reviewId: string): Promise<Review> {
  const { data } = await apiClient.get<ApiResponse<Review>>(`/v1/reviews/details/${reviewId}`);
  return data.data;
}

// ============================================================
// DASHBOARD SERVICES
// ============================================================

/**
 * Получение сводки дашборда
 * Эндпоинт: GET /api/v1/reviews/summary
 */
export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummaryResponse>('/v1/reviews/summary');
  return data.data;
}

// ============================================================
// PARSER SERVICES
// ============================================================

/**
 * Запуск задачи парсинга отзывов
 * POST /api/v1/parser/start
 * Body: { platform: "2gis" | "yandex" | "google", url: "https://..." }
 * Response: 202 Accepted { job_id: "uuid" }
 */
export async function startParserJob(jobRequest: ParserJobRequest): Promise<{ job_id: string }> {
  const { data } = await apiClient.post<{ job_id: string }>('/v1/parser/start', jobRequest);
  return data;
}

/**
 * Получение статуса задачи парсинга
 * GET /api/v1/parser/jobs/{job_id}
 * Response: { job_id, state, result, error }
 */
export async function getParserJobStatus(jobId: string): Promise<ParserJobResponse> {
  const { data } = await apiClient.get<ParserJobResponse>(`/v1/parser/jobs/${jobId}`);
  return data;
}

// ============================================================
// QUOTAS & BILLING SERVICES
// ============================================================

/**
 * Получение статуса квот текущего tenant'а
 * GET /api/v1/quotas/status
 * Response: QuotaStatus
 */
export async function getQuotaStatus(): Promise<QuotaStatus> {
  const { data } = await apiClient.get<QuotaStatus>('/v1/quotas/status');
  
  // Compute derived properties if missing
  const totalTokens = data.usage.used_llm_tokens + data.usage.reserved_llm_tokens;
  
  return {
    ...data,
    total_tokens_committed: totalTokens,
    tokens_available: Math.max(0, data.limits.max_llm_tokens - totalTokens),
    reviews_available: Math.max(0, data.limits.max_reviews - data.usage.used_reviews),
    tokens_usage_percent: data.limits.max_llm_tokens > 0 
      ? (totalTokens / data.limits.max_llm_tokens) * 100 
      : 0,
    reviews_usage_percent: data.limits.max_reviews > 0
      ? (data.usage.used_reviews / data.limits.max_reviews) * 100
      : 0,
  };
}


// ============================================================
// API KEYS SERVICES
// ============================================================

/**
 * Получение списка API ключей текущего tenant
 * GET /api/v1/api-keys
 */
export async function getAPIKeys(): Promise<APIKey[]> {
  const { data } = await apiClient.get<APIKey[]>('/v1/api-keys');
  return data;
}

/**
 * Создание нового API ключа
 * POST /api/v1/api-keys
 * ВАЖНО: Полный ключ возвращается только один раз!
 */
export async function createAPIKey(request: CreateAPIKeyRequest): Promise<CreateAPIKeyResponse> {
  const { data } = await apiClient.post<CreateAPIKeyResponse>('/v1/api-keys', request);
  return data;
}

/**
 * Отзыв (удаление) API ключа
 * DELETE /api/v1/api-keys/{key_id}
 */
export async function revokeAPIKey(keyId: string): Promise<void> {
  await apiClient.delete(`/v1/api-keys/${keyId}`);
}

// ============================================================
// WEBHOOKS SERVICES
// ============================================================

/**
 * Получение списка вебхуков текущего tenant
 * GET /api/v1/webhooks
 */
export async function getWebhooks(): Promise<Webhook[]> {
  const { data } = await apiClient.get<Webhook[]>('/v1/webhooks');
  return data;
}

/**
 * Создание нового вебхука
 * POST /api/v1/webhooks
 * ВАЖНО: Полный secret_key возвращается только один раз!
 */
export async function createWebhook(request: CreateWebhookRequest): Promise<CreateWebhookResponse> {
  const { data } = await apiClient.post<CreateWebhookResponse>('/v1/webhooks', request);
  return data;
}

/**
 * Удаление вебхука
 * DELETE /api/v1/webhooks/{webhook_id}
 */
export async function deleteWebhook(webhookId: string): Promise<void> {
  await apiClient.delete(`/v1/webhooks/${webhookId}`);
}

// ============================================================
// ANALYTICS EXPORT SERVICES
// ============================================================

/**
 * Экспорт аналитики в CSV
 * GET /api/v1/analytics/export
 * Возвращает файл для скачивания
 */
export async function exportAnalyticsToCSV(params?: { days?: number }): Promise<Blob> {
  const response = await apiClient.get('/v1/analytics/export', {
    params,
    responseType: 'blob',
  });
  return response.data;
}
