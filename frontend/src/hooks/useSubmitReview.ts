/**
 * useSubmitReview — mutation for manual review submission with AbortController
 *
 * Features:
 * - Axios integration with TanStack Query
 * - AbortController for request cancellation on unmount or cancel button
 * - Automatic cleanup on component unmount
 * - Error handling with UI feedback
 */

import { useEffect, useRef } from 'react';
import { useMutation, useQueryClient, type UseMutationOptions } from '@tanstack/react-query';

import { apiClient } from '@/api/client';
import { reviewsKeys } from '@/hooks/api/useReviews';
import type { Review } from '@/api/services';

export interface SubmitReviewInput {
  platform: string;
  author_name?: string;
  rating: number;
  text: string;
  tags?: string[];
}

export interface SubmitReviewContext {
  previousData?: unknown;
}

/**
 * Submit a new review with network cancellation support
 *
 * This hook implements proper AbortController pattern:
 * - Creates a new AbortController for each mutation
 * - Automatically aborts on component unmount
 * - Provides cancel function for manual cancellation
 *
 * @param options Optional TanStack Query mutation options
 * @returns Mutation with submit function, cancel, and status
 */
export function useSubmitReview(
  options?: Omit<
    UseMutationOptions<Review, Error, SubmitReviewInput, SubmitReviewContext>,
    'mutationFn'
  >
) {
  const queryClient = useQueryClient();
  const controllerRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Abort any pending request when component unmounts
      if (controllerRef.current) {
        controllerRef.current.abort();
      }
    };
  }, []);

  const mutation = useMutation<Review, Error, SubmitReviewInput, SubmitReviewContext>({
    mutationFn: async (data) => {
      // Create new AbortController for this request
      const controller = new AbortController();
      controllerRef.current = controller;
      const signal = controller.signal;

      try {
        const response = await apiClient.post<Review>('/api/v1/reviews', data, {
          signal,
        });
        return response.data;
      } catch (error) {
        // Check if error is due to cancellation
        if (controller.signal.aborted) {
          throw new Error('Request cancelled');
        }
        throw error;
      } finally {
        // Clear controller after request completes
        controllerRef.current = null;
      }
    },

    onSuccess: (data, variables, context) => {
      // Invalidate reviews cache to fetch new data
      queryClient.invalidateQueries({ queryKey: reviewsKeys.all });
      options?.onSuccess?.(data, variables, context);
    },

    onError: (error, variables, context) => {
      // Don't log if it's a cancellation
      if (error.message !== 'Request cancelled') {
        console.error('Failed to submit review:', error);
      }
      options?.onError?.(error, variables, context);
    },

    onSettled: (data, error, variables, context) => {
      options?.onSettled?.(data, error, variables, context);
    },
  });

  /**
   * Manually cancel the current request
   */
  const cancel = () => {
    if (controllerRef.current) {
      controllerRef.current.abort();
      controllerRef.current = null;
    }
  };

  return {
    ...mutation,
    cancel,
  };
}
