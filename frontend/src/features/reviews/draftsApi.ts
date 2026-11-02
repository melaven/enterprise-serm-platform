import { apiClient } from '@/api/services';

export type DraftStrategy = 'LEGAL_STRICT' | 'APPEASEMENT' | 'INFO_REQUEST';
export type ReplyPublicationStatus =
  | 'queued_outbox'
  | 'publishing'
  | 'published'
  | 'publish_failed';

export interface ReplyResponse {
  readonly status: ReplyPublicationStatus | null;
  readonly external_reply_id: string | null;
  readonly failure_reason: string | null;
}

export interface DraftResponse extends ReplyResponse {
  readonly id: string;
  readonly strategy: DraftStrategy;
  readonly body: string;
  readonly is_approved: boolean;
  readonly approved_by: string | null;
  readonly approved_at: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

export async function fetchReviewDrafts(
  reviewId: string,
  signal?: AbortSignal,
): Promise<DraftResponse[]> {
  const response = await apiClient.get<DraftResponse[]>(
    `/v1/reviews/${encodeURIComponent(reviewId)}/drafts`,
    signal ? { signal } : undefined,
  );
  return response.data;
}

export async function retryReplyPublication(
  reviewId: string,
  draftId: string,
): Promise<void> {
  await apiClient.post(
    `/v1/reviews/${encodeURIComponent(reviewId)}/drafts/${encodeURIComponent(draftId)}/retry-publication`,
  );
}
