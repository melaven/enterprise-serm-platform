/**
 * Optimistic mutation for archiving a review.
 *
 * This hook demonstrates:
 * - Type-safe API calls through apiClient
 * - Optimistic cache updates with rollback on error
 * - Query key factory usage for cache invalidation
 * - Signal support for request cancellation
 */

import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query';

import { apiClient, type Review } from '@/api/services';
import { reviewsKeys } from '@/hooks/api/useReviews';

interface ArchiveReviewVariables {
  reviewId: string;
}

interface ArchiveReviewContext {
  previousData: Map<QueryKey, unknown>;
}

/**
 * Archive a review with optimistic UI updates.
 *
 * This hook:
 * 1. Immediately removes the review from the UI (optimistic update)
 * 2. Sends the archive request to the backend
 * 3. Rolls back if the request fails
 * 4. Refetches on success to ensure consistency
 */
export function useArchiveReview() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, ArchiveReviewVariables, ArchiveReviewContext>({
    mutationFn: async ({ reviewId }) => {
      await apiClient.post(`/api/v1/reviews/${reviewId}/archive`);
    },

    onMutate: async ({ reviewId }) => {
      // Step 1: Cancel any outgoing refetches for all reviews queries
      await queryClient.cancelQueries({ queryKey: reviewsKeys.all });

      // Step 2: Snapshot the previous state for all matching queries
      const queryCache = queryClient.getQueryCache();
      const previousData = new Map<QueryKey, unknown>();
      queryCache.findAll({ queryKey: reviewsKeys.all }).forEach((query) => {
        previousData.set(query.queryKey, query.state.data);
      });

      // Step 3: Optimistically update the cache - remove the archived review
      queryCache.findAll({ queryKey: reviewsKeys.all }).forEach((query) => {
        queryClient.setQueryData(query.queryKey, (old: any) => {
          if (!old) return old;

          // Handle paginated response structure
          if (old.items && Array.isArray(old.items)) {
            return {
              ...old,
              items: old.items.filter((review: Review) => review.id !== reviewId),
              total: Math.max(0, old.total - 1),
            };
          }

          // Handle array response structure
          if (Array.isArray(old)) {
            return old.filter((review: Review) => review.id !== reviewId);
          }

          return old;
        });
      });

      // Step 4: Return context with the previous values for rollback
      return { previousData };
    },

    onError: (_error, _variables, context) => {
      // Roll back to the previous values on error
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
