import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from 'axios';

import { parseQuotaExceeded, quotaStore, type QuotaExceededInfo } from './quota';
import { parseRetryAfter, rateLimitStore } from './rateLimit';
import { shouldAttachToken, type TokenStore } from './token';

declare module 'axios' {
  interface AxiosRequestConfig {
    /** true: 402 не открывает глобальную модалку (фоновые опросы квот, prefetch). */
    skipQuotaDialog?: boolean;
  }
}

// --------------------------------------------------------------------------- //
// Ошибки: UI работает с типизированными исключениями, а не с AxiosError
// --------------------------------------------------------------------------- //
export class ApiError extends Error {
  readonly status: number; // 0: сети нет / таймаут
  readonly code: 'NETWORK' | 'TIMEOUT' | 'HTTP';
  readonly correlationId: string | null; // X-Correlation-ID: отдаётся в поддержку

  constructor(
    message: string,
    status: number,
    code: 'NETWORK' | 'TIMEOUT' | 'HTTP',
    correlationId: string | null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
  }
}

/** HTTP 402: квота исчерпана или подписка неактивна. */
export class QuotaExceededApiError extends ApiError {
  readonly info: QuotaExceededInfo;

  constructor(info: QuotaExceededInfo, correlationId: string | null) {
    super(info.message, 402, 'HTTP', correlationId);
    this.name = 'QuotaExceededApiError';
    this.info = info;
  }
}

/** HTTP 429: слишком много запросов, нужен retry. */
export class RateLimitedApiError extends ApiError {
  readonly retryAfterSeconds: number;

  constructor(message: string, retryAfterSeconds: number, correlationId: string | null) {
    super(message, 429, 'HTTP', correlationId);
    this.name = 'RateLimitedApiError';
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function headerValue(value: unknown): string | null {
  return typeof value === 'string' && value !== '' ? value : null;
}

/** FastAPI кладёт тело ошибки в `detail`: строка или объект. */
function extractMessage(data: unknown): string | null {
  const detail =
    typeof data === 'object' && data !== null && 'detail' in data
      ? (data as { detail: unknown }).detail
      : data;
  return typeof detail === 'string' && detail !== '' ? detail : null;
}

export function toApiError(error: AxiosError): ApiError {
  const correlationId = headerValue(error.response?.headers?.['x-correlation-id']);

  if (!error.response) {
    const timeout = error.code === AxiosError.ECONNABORTED || error.code === AxiosError.ETIMEDOUT;
    return new ApiError(
      timeout ? 'Сервер не ответил вовремя' : 'Нет соединения с сервером',
      0,
      timeout ? 'TIMEOUT' : 'NETWORK',
      null,
    );
  }

  const { status, data } = error.response;
  
  if (status === 402) {
    return new QuotaExceededApiError({ ...parseQuotaExceeded(data), correlationId }, correlationId);
  }
  
  if (status === 429) {
    const retryAfter = parseRetryAfter(error.response.headers?.['retry-after']) ?? 15;
    return new RateLimitedApiError(
      extractMessage(data) ?? 'Слишком много запросов',
      retryAfter,
      correlationId,
    );
  }
  
  return new ApiError(
    extractMessage(data) ?? `Ошибка запроса (${status})`,
    status,
    'HTTP',
    correlationId,
  );
}

// --------------------------------------------------------------------------- //
// Клиент
// --------------------------------------------------------------------------- //
export interface ApiClientOptions {
  baseURL: string;
  tokens: TokenStore;
  /** Вызывается на 401 (токен уже очищен): редирект на логин. */
  onUnauthorized?: () => void;
  timeoutMs?: number;
  /** Для тестов. */
  adapter?: AxiosAdapter;
}

export function createApiClient(options: ApiClientOptions): AxiosInstance {
  const { baseURL, tokens, onUnauthorized, timeoutMs = 15_000, adapter } = options;
  const client = axios.create({ baseURL, timeout: timeoutMs, adapter });
  const pageOrigin = typeof location === 'undefined' ? 'http://localhost' : location.origin;

  // Запрос: Authorization: Bearer <JWT> для RLS-бэкенда.
  client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const headers = AxiosHeaders.from(config.headers);
    if (!headers.has('Authorization') && shouldAttachToken(config.url, config.baseURL, pageOrigin)) {
      const token = tokens.get();
      if (token !== null) headers.set('Authorization', `Bearer ${token}`);
    }
    config.headers = headers;
    return config;
  });

  // Ответ: единый тип ошибок; 401 сбрасывает токен; 402 открывает модалку; 429 запускает таймер.
  client.interceptors.response.use(
    (response) => response,
    (error: unknown) => {
      if (!(error instanceof AxiosError) || axios.isCancel(error)) return Promise.reject(error);
      const apiError = toApiError(error);

      if (apiError.status === 401) {
        tokens.clear();
        onUnauthorized?.();
      } else if (apiError instanceof QuotaExceededApiError && !error.config?.skipQuotaDialog) {
        quotaStore.open(apiError.info);
      } else if (apiError instanceof RateLimitedApiError) {
        rateLimitStore.open(apiError.retryAfterSeconds, apiError.correlationId);
      }
      
      return Promise.reject(apiError);
    },
  );

  return client;
}
