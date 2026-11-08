import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiClient } from '@/api/services';
import { reviewsKeys } from './api/useReviews';

/**
 * Hook for approving SI-generated reply
 * 
 * Connects to POST /api/v1/reviews/{review_id}/approve
 * Handles optimistic updates and error rollback
 */

interface ApproveReplyInput {
  reviewId: string;
  content: string;
}

interface ApproveReplyResponse {
  review_id: string;
  reply_status: string;
}

export function useApproveReply() {
  const queryClient = useQueryClient();

  return useMutation<
    ApproveReplyResponse,
    Error,
    ApproveReplyInput,
    { previousData: unknown }
  >({
    mutationFn: async ({ reviewId, content }) => {
      const response = await apiClient.post<ApproveReplyResponse>(
        `/v1/reviews/${reviewId}/approve`,
        { content }
      );
      return response.data;
    },
    onMutate: async ({ reviewId }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: reviewsKeys.all });

      // Snapshot the previous value
      const previousData = queryClient.getQueryData(reviewsKeys.all);

      // Optimistically update to the new value
      queryClient.setQueriesData({ queryKey: reviewsKeys.all }, (old: any) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items?.map((review: any) =>
            review.id === reviewId
              ? { ...review, moderation_status: 'published' }
              : review
          ),
        };
      });

      return { previousData };
    },
    onError: (error, _variables, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(reviewsKeys.all, context.previousData);
      }
      
      toast.error('Ошибка при утверждении ответа', {
        description: error.message || 'Попробуйте снова',
      });
    },
    onSuccess: () => {
      toast.success('Ответ утвержден', {
        description: 'SI-ответ успешно опубликован',
      });
    },
    onSettled: () => {
      // Always refetch to ensure sync with server
      queryClient.invalidateQueries({ queryKey: reviewsKeys.all });
    },
  });
}
