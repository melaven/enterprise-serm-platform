/**
 * Type-safe reviews hooks using openapi-fetch.
 * 
 * This demonstrates how to use the generated OpenAPI types with TanStack Query
 * for full end-to-end type safety. All request parameters and response payloads
 * are automatically inferred from the backend schema.
 * 
 * Benefits:
 * - No manual type definitions needed
 * - Compile-time errors if backend schema changes
 * - IDE autocomplete for all API endpoints
 * - Full type inference in useQuery/useMutation
 */

import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query';

import * as demoApi from '@/api/demoService';
import { api, createOpenAPIClient } from '@/api/openapi-client';
import { useAppStore } from '@/store/useAppStore';

export interface ReviewQueryParams {
  page?: number;
  page_size?: number;
  platform?: string;
  sentiment?: string;
  search?: string;
}

export const reviewsQueryKey = ['reviews'] as const;
export const reviewDraftsQueryKey = ['review-drafts'] as const;
export const dashboardSummaryQueryKey = ['dashboard-summary'] as const;

const isDemoMode =
  import.meta.env.VITE_DEMO_MODE === 'true' || import.meta.env.VITE_USE_MOCKS === 'true';

/**
 * Fetch reviews with full type safety.
 * 
 * The request parameters and response type are automatically inferred from the
 * OpenAPI schema. If the backend changes the schema, TypeScript will catch it
 * at compile time.
 */
export function useReviewsOpenAPI(params: ReviewQueryParams = {}) {
  const tenantId = useAppStore((state) => state.user?.tenant_id ?? null);

  return useQuery({
    queryKey: [...reviewsQueryKey, tenantId, params],
    queryFn: async ({ signal }) => {
      if (isDemoMode) {
        return demoApi.getReviews(params, signal);
      }

      // Type-safe API call - all parameters are validated by TypeScript
      const { data, error } = await api.getReviews({
        query: params,
      });

      if (error) {
        throw error;
      }

      // TypeScript infers the exact response structure from the schema
      return data;
    },
    enabled: tenantId !== null,
  });
}

/**
 * Fetch dashboard summary with type safety.
 */
export function useDashboardSummaryOpenAPI() {
  const tenantId = useAppStore((state) => state.user?.tenant_id ?? null);

  return useQuery({
    queryKey: [...dashboardSummaryQueryKey, tenantId],
    queryFn: async ({ signal }) => {
      if (isDemoMode) {
        return demoApi.getDashboardSummary(signal);
      }

      const { data, error } = await api.getDashboardSummary();

      if (error) {
        throw error;
      }

      return data;
    },
    enabled: tenantId !== null,
  });
}

/**
 * Update review status with type-safe mutation.
 * 
 * The request body and response are fully typed from the OpenAPI schema.
 * TanStack Query automatically infers the mutation variables type.
 */
export function useUpdateReviewStatusOpenAPI() {
  const queryClient = useQueryClient();

  return useMutation<
    void,
    Error,
    {
      reviewId: string;
      newStatus: 'new' | 'si_processing' | 'resolved' | 'lost';
      siResponse?: string;
    },
    { previousData: Map<QueryKey, unknown> }
  >({
    mutationFn: async ({ reviewId, newStatus, siResponse }) => {
      // Type-safe API call - TypeScript validates the body structure
      const { data, error } = await api.updateReviewStatus(reviewId, {
        new_status: newStatus,
        si_response: siResponse,
      });

      if (error) {
        throw error;
      }

      return data;
    },
    onMutate: async ({ reviewId, newStatus, siResponse }) => {
      // Cancel any outgoing refetches for all reviews queries
      await queryClient.cancelQueries({ queryKey: reviewsQueryKey });

      // Snapshot the previous state for all matching queries
      const queryCache = queryClient.getQueryCache();
      const previousData = new Map<QueryKey, unknown>();
      queryCache.findAll({ queryKey: reviewsQueryKey }).forEach((query) => {
        previousData.set(query.queryKey, query.state.data);
      });

      // Optimistically update the cache for all matching queries
      queryCache.findAll({ queryKey: reviewsQueryKey }).forEach((query) => {
        queryClient.setQueryData(query.queryKey, (old: any) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items?.map((review: any) =>
              review.id === reviewId
                ? {
                    ...review,
                    status: newStatus,
                    si_response: siResponse ?? review.si_response,
                  }
                : review
            ),
          };
        });
      });

      // Return context with the previous values
      return { previousData };
    },
    onError: (
      _error,
      _variables,
      context: { previousData: Map<QueryKey, unknown> } | undefined,
    ) => {
      // Roll back to the previous values
      if (context?.previousData) {
        context.previousData.forEach((data, queryKey) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
    },
    onSettled: async () => {
      // Always refetch to ensure sync with server
      await queryClient.invalidateQueries({ queryKey: reviewsQueryKey });
    },
  });
}

/**
 * Generate AI reply with type-safe mutation.
 * 
 * Demonstrates how the response type is automatically inferred from the schema.
 */
export function useGenerateReplyOpenAPI() {
  return useMutation({
    mutationFn: async (reviewId: string) => {
      const { data, error } = await api.generateReply(reviewId);

      if (error) {
        throw error;
      }

      // TypeScript knows the exact structure of the response
      return data;
    },
  });
}

/**
 * Submit moderation with type-safe mutation.
 */
export function useSubmitModerationOpenAPI() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ reviewId, resolvedText }: { reviewId: string; resolvedText: string }) => {
      const { data, error } = await api.submitModeration(reviewId, {
        resolved_text: resolvedText,
      });

      if (error) {
        throw error;
      }

      return data;
    },
    onSuccess: () => {
      // Invalidate queries to refresh the list
      queryClient.invalidateQueries({ queryKey: reviewsQueryKey });
    },
  });
}

/**
 * Example: Authenticated API client usage.
 * 
 * This shows how to pass the JWT token for authenticated requests.
 */
export function useAuthenticatedReviews() {
  const tenantId = useAppStore((state) => state.user?.tenant_id ?? null);
  const token = useAppStore((state) => state.token);

  return useQuery({
    queryKey: [...reviewsQueryKey, tenantId, 'authenticated'],
    queryFn: async ({ signal }) => {
      if (!token) {
        throw new Error('Authentication required');
      }

      // Create authenticated client
      const client = createOpenAPIClient(token);

      // Use the authenticated client
      const { data, error } = await client.GET('/api/v1/reviews', {
        params: { query: { page: 1, page_size: 50 } },
        signal,
      });

      if (error) {
        throw error;
      }

      return data;
    },
    enabled: tenantId !== null && token !== null,
  });
}
