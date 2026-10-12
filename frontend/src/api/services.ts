/**
 * Централизованный слой API сервисов
 * Все взаимодействия с backend происходят через эти функции
 */

import { apiClient } from './client';

// ============================================================
// ТИПЫ
// ============================================================

export interface Review {
  id: string;
  external_review_id: string;
  source: string;
  author: string;
  rating: number;
  text: string;
  date: string;
  url: string | null;
  sentiment: string | null;
  topics: string[] | null;
  created_at: string;
}

export interface AnalyticsSummary {
  total_reviews: number;
  avg_rating: number;
  sentiment_distribution: {
    positive: number;
    neutral: number;
    negative: number;
  };
  top_topics: Array<{
    topic: string;
    count: number;
  }>;
  rating_distribution: {
    [key: string]: number;
  };
}

export interface ParserJobRequest {
  url: string;
  company_id: string;
  limit?: number;
}

export interface ParserJobResponse {
  job_id: string;
  status: string;
  message: string;
  platform_url: string;
  company_id: string;
  limit: number;
  quota_info: {
    estimated_tokens: number;
    used: number;
    limit: number;
  };
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

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  user: {
    id: string;
    email: string;
    tenant_id?: string;
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

  const { data } = await apiClient.post<AuthResponse>('/api/v1/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  });
  return data;
}

/**
 * Регистрация нового пользователя
 */
export async function register(userData: RegisterRequest): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>('/api/v1/auth/register', userData);
  return data;
}

/**
 * Получение профиля текущего пользователя
 */
export async function getCurrentUser(): Promise<UserProfile> {
  const { data } = await apiClient.get<UserProfile>('/api/v1/auth/me');
  return data;
}

/**
 * Выход из системы
 */
export async function logout(): Promise<void> {
  await apiClient.post('/api/v1/auth/logout');
}

/**
 * Обновление access token через refresh token
 */
export async function refreshToken(refresh_token: string): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>('/api/v1/auth/refresh', { refresh_token });
  return data;
}

// ============================================================
// REVIEWS SERVICES
// ============================================================

/**
 * Получение списка отзывов с пагинацией
 */
export async function getReviews(params?: {
  skip?: number;
  limit?: number;
  source?: string;
  sentiment?: string;
}): Promise<Review[]> {
  const { data } = await apiClient.get<Review[]>('/api/v1/reviews/', { params });
  return data;
}

/**
 * Получение отзыва по ID
 */
export async function getReviewById(reviewId: string): Promise<Review> {
  const { data } = await apiClient.get<Review>(`/api/v1/reviews/${reviewId}`);
  return data;
}

// ============================================================
// ANALYTICS SERVICES
// ============================================================

/**
 * Получение аналитической сводки
 */
export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  const { data } = await apiClient.get<AnalyticsSummary>('/api/v1/analytics/summary');
  return data;
}

// ============================================================
// PARSER SERVICES
// ============================================================

/**
 * Запуск задачи парсинга отзывов
 */
export async function startParserJob(jobRequest: ParserJobRequest): Promise<ParserJobResponse> {
  const { data } = await apiClient.post<ParserJobResponse>('/api/v1/parsers/start', jobRequest);
  return data;
}

/**
 * Получение статуса задачи парсинга
 */
export async function getParserJobStatus(jobId: string): Promise<ParserJobResponse> {
  const { data } = await apiClient.get<ParserJobResponse>(`/api/v1/parsers/status/${jobId}`);
  return data;
}
