/**
 * Type-safe API client using openapi-fetch.
 * 
 * This client provides full type safety by generating TypeScript types from the OpenAPI schema.
 * All request parameters and response payloads are automatically inferred from the backend schema.
 * 
 * Installation:
 * 1. Run `npm run typegen` to generate schema.d.ts from http://localhost:8000/openapi.json
 * 2. Ensure the FastAPI backend is running locally on port 8000
 * 
 * Usage:
 * ```ts
 * import createClient from '@/api/openapi-client';
 * 
 * const client = createClient();
 * 
 * // GET request with typed parameters and response
 * const { data, error } = await client.GET('/api/v1/reviews', {
 *   params: {
 *     query: { page: 1, page_size: 50 }
 *   }
 * });
 * 
 * // POST request with typed body
 * const { data, error } = await client.POST('/api/v1/reviews', {
 *   body: {
 *     platform_id: 'uuid',
 *     rating: 5,
 *     text: 'Great service!'
 *   }
 * });
 * ```
 */

import createClient from 'openapi-fetch';
import type { paths } from './schema';

// schema.d.ts is a placeholder until the backend OpenAPI types are generated.
// Keep the client usable in the meantime; generated paths restore endpoint typing.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ClientPaths = keyof paths extends never ? any : paths;

// Base URL for the API - can be configured via environment variable
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Create a type-safe API client with authentication support.
 * 
 * @param token - Optional JWT bearer token for authenticated requests
 * @returns Configured openapi-fetch client
 */
export function createOpenAPIClient(token?: string) {
  const client = createClient<ClientPaths>({
    baseUrl: BASE_URL,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  return client;
}

/**
 * Default client instance (unauthenticated).
 * For authenticated requests, use createOpenAPIClient(token) instead.
 */
export const apiClient = createOpenAPIClient();

/**
 * Type-safe API methods for common operations.
 * These are convenience wrappers around the raw client.
 */
export const api = {
  /**
   * Get paginated list of reviews.
   */
  getReviews: async (params?: {
    query?: {
      page?: number;
      page_size?: number;
      platform?: string;
      sentiment?: string;
      search?: string;
    };
  }) => {
    const client = createOpenAPIClient();
    return client.GET('/api/v1/reviews', { params });
  },

  /**
   * Get a single review by ID.
   */
  getReview: async (reviewId: string) => {
    const client = createOpenAPIClient();
    return client.GET('/api/v1/reviews/{review_id}', {
      params: { path: { review_id: reviewId } },
    });
  },

  /**
   * Create a new review.
   */
  createReview: async (body: {
    platform_id: string;
    rating: number;
    text: string;
  }) => {
    const client = createOpenAPIClient();
    return client.POST('/api/v1/reviews', { body });
  },

  /**
   * Update review status.
   */
  updateReviewStatus: async (
    reviewId: string,
    body: {
      new_status: 'new' | 'si_processing' | 'resolved' | 'lost';
      si_response?: string;
    }
  ) => {
    const client = createOpenAPIClient();
    return client.PUT('/api/v1/reviews/{review_id}/status', {
      params: { path: { review_id: reviewId } },
      body,
    });
  },

  /**
   * Generate AI reply for a review.
   */
  generateReply: async (reviewId: string) => {
    const client = createOpenAPIClient();
    return client.POST('/api/v1/reviews/{review_id}/generate-reply', {
      params: { path: { review_id: reviewId } },
    });
  },

  /**
   * Submit moderation for a review reply.
   */
  submitModeration: async (reviewId: string, body: { resolved_text: string }) => {
    const client = createOpenAPIClient();
    return client.POST('/api/v1/reviews/{review_id}/submit-moderation', {
      params: { path: { review_id: reviewId } },
      body,
    });
  },

  /**
   * Get dashboard summary metrics.
   */
  getDashboardSummary: async () => {
    const client = createOpenAPIClient();
    return client.GET('/api/v1/analytics/dashboard', {});
  },
};

// Re-export types for convenience
export type { paths };
