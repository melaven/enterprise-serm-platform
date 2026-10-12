import { createApiClient } from './client.ts';
import { createParserApi } from './parser.ts';
import { createReviewsApi } from './reviews.ts';
import { TokenStore } from './token.ts';

export const tokens = new TokenStore(typeof localStorage === 'undefined' ? null : localStorage);

export const api = createApiClient({
  baseURL: import.meta.env.VITE_API_URL ?? '',
  tokens,
  onUnauthorized: () => {
    if (location.pathname !== '/login') location.assign('/login');
  },
});

/** Все вызовы парсера идут через `api` (JWT + интерцептор 402). Локальных fetch нет. */
export const parserApi = createParserApi(api);

/** GET /reviews и /reviews/summary: тоже через `api` (JWT + интерцептор 402). */
export const reviewsApi = createReviewsApi(api);

export { ApiError, QuotaExceededApiError } from './client.ts';
export { quotaStore, parseQuotaExceeded, type QuotaExceededInfo } from './quota.ts';
