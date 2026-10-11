/**
 * Базовые типы для API взаимодействия
 */

export interface ApiError {
  detail: string;
  code?: string;
  field?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export interface User {
  id: string;
  email: string;
  tenant_id: string;
  created_at: string;
}

export interface QuotaStatus {
  llm_tokens: {
    used: number;
    limit: number;
    percentage: number;
  };
  parsing_requests: {
    used: number;
    limit: number;
    percentage: number;
  };
  period_start: string;
  period_end: string;
}
