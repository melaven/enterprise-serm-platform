import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query';

import * as demoApi from '@/api/demoService';
import { fetchReviews as fetchSanitizedReviews } from '@/api/reviews';
import {
  getDashboardSummary,
  getReviews,
  updateReviewStatus,
  type Review,
} from '@/api/services';
import { approveDraft } from '@/features/reviews/approveDraftApi';
import type { ApproveRequest, ApproveResult } from '@/features/reviews/approveDraftLogic';
import { useAppStore } from '@/store/useAppStore';
import type { SanitizedReview } from '@/types/review';

export interface ReviewQueryParams {
  page?: number;
  page_size?: number;
  platform?: string;
  sentiment?: string;
  search?: string;
}

// ============================================
// Query Keys Factory
// ============================================
export const reviewsKeys = {
  all: ['reviews'] as const,
  lists: () => [...reviewsKeys.all, 'list'] as const,
  list: (params: ReviewQueryParams) => [...reviewsKeys.lists(), params] as const,
  details: () => [...reviewsKeys.all, 'detail'] as const,
  detail: (id: string) => [...reviewsKeys.details(), id] as const,
} as const;

export const reviewDraftsQueryKey = ['review-drafts'] as const;
export const dashboardSummaryQueryKey = ['dashboard-summary'] as const;

// Backward compatibility - can be removed after migration
export const reviewsQueryKey = reviewsKeys.all;

const isDemoMode =
  import.meta.env.VITE_DEMO_MODE === 'true' || import.meta.env.VITE_USE_MOCKS === 'true';

export function useReviews(params: ReviewQueryParams = {}) {
  const tenantId = useAppStore((state) => state.user?.tenant_id ?? null);

  return useQuery({
    queryKey: [...reviewsKeys.all, tenantId, params],
    queryFn: ({ signal }) =>
      isDemoMode
        ? demoApi.getReviews(params, signal)
        : getReviews(params, signal),
    enabled: tenantId !== null,
    refetchInterval: (query) =>
      query.state.data?.items.some(
        (review) =>
          review.generated_reply === null || review.generated_reply === undefined,
      )
        ? 3_000
        : false,
    refetchIntervalInBackground: true,
  });
}

export function usePlatformReviews(
  companyId: string | null,
  platform: string | null,
) {
  return useQuery<SanitizedReview[]>({
    queryKey: [...reviewsQueryKey, 'sanitized', companyId, platform],
    queryFn: ({ signal }) => {
      if (companyId === null) {
        throw new Error('A company is required to fetch platform reviews.');
      }
      return fetchSanitizedReviews(companyId, platform, signal);
    },
    enabled: companyId !== null,
    refetchInterval: 15_000,
    staleTime: 0,
  });
}

export function useDashboardSummary() {
  const tenantId = useAppStore((state) => state.user?.tenant_id ?? null);

  return useQuery({
    queryKey: [...dashboardSummaryQueryKey, tenantId],
    queryFn: ({ signal }) =>
      isDemoMode
        ? demoApi.getDashboardSummary(signal)
        : getDashboardSummary(signal),
    enabled: tenantId !== null,
  });
}

export function useApproveDraft() {
  const queryClient = useQueryClient();

  return useMutation<
    ApproveResult,
    Error,
    ApproveRequest,
    { previousData: Map<QueryKey, unknown> }
  >({
    mutationFn: (request) => approveDraft(request),
    onMutate: async (request) => {
      // Cancel any outgoing refetches for all reviews queries
      await queryClient.cancelQueries({ queryKey: reviewsKeys.all });

      // Snapshot the previous state for all matching queries
      const queryCache = queryClient.getQueryCache();
      const previousData = new Map<QueryKey, unknown>();
      queryCache.findAll({ queryKey: reviewsKeys.all }).forEach((query) => {
        previousData.set(query.queryKey, query.state.data);
      });

      // Optimistically update the cache for all matching queries
      queryCache.findAll({ queryKey: reviewsKeys.all }).forEach((query) => {
        queryClient.setQueryData(query.queryKey, (old: any) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items?.map((review: Review) =>
              review.id === request.reviewId
                ? { ...review, status: 'resolved' as Review['status'] }
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
    onSettled: async (_result, _error, request) => {
      // Always refetch to ensure sync with server
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: reviewsKeys.all }),
        queryClient.invalidateQueries({
          queryKey: [...reviewDraftsQueryKey, request.reviewId],
        }),
      ]);
    },
  });
}

export interface UpdateReviewStatusInput {
  reviewId: string;
  newStatus: Review['status'];
  siResponse?: string;
}

export function useUpdateReviewStatus() {
  const queryClient = useQueryClient();

  return useMutation<
    void,
    Error,
    UpdateReviewStatusInput,
    { previousData: Map<QueryKey, unknown> }
  >({
    mutationFn: ({ reviewId, newStatus, siResponse }) =>
      updateReviewStatus(reviewId, newStatus, siResponse),
    onMutate: async ({ reviewId, newStatus, siResponse }) => {
      // Cancel any outgoing refetches for all reviews queries
      await queryClient.cancelQueries({ queryKey: reviewsKeys.all });

      // Snapshot the previous state for all matching queries
      const queryCache = queryClient.getQueryCache();
      const previousData = new Map<QueryKey, unknown>();
      queryCache.findAll({ queryKey: reviewsKeys.all }).forEach((query) => {
        previousData.set(query.queryKey, query.state.data);
      });

      // Optimistically update the cache for all matching queries
      queryCache.findAll({ queryKey: reviewsKeys.all }).forEach((query) => {
        queryClient.setQueryData(query.queryKey, (old: any) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items?.map((review: Review) =>
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
      await queryClient.invalidateQueries({ queryKey: reviewsKeys.all });
    },
  });
}
