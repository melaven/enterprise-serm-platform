import { apiClient } from './services';
import type { SanitizedReview } from '@/types/review';

interface ReviewsResponse {
  success: boolean;
  data: {
    items: SanitizedReview[];
  };
}

export async function fetchReviews(
  companyId: string,
  platform: string | null,
  signal?: AbortSignal,
): Promise<SanitizedReview[]> {
  const response = await apiClient.get<ReviewsResponse>('/v1/reviews', {
    params: {
      company_id: companyId,
      platform: platform ?? undefined,
      page: 1,
      page_size: 100,
    },
    signal,
  });

  return response.data.data.items;
}

interface GenerateReplyResponse {
  review_id: string;
  suggested_reply: string;
}

export async function generateReviewReply(reviewId: string): Promise<string> {
  const response = await apiClient.post<GenerateReplyResponse>(
    `/v1/reviews/${reviewId}/generate-reply`,
  );

  return response.data.suggested_reply;
}
