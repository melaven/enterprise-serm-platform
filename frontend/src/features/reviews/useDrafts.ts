import { useQuery } from '@tanstack/react-query';

import { reviewDraftsQueryKey } from '@/hooks/api/useReviews';
import { fetchReviewDrafts, type DraftResponse } from './draftsApi';

const TRANSIT_POLL_INTERVAL_MS = 4_000;
const IDLE_POLL_INTERVAL_MS = 20_000;

function hasPendingPublication(drafts: readonly DraftResponse[]): boolean {
  return drafts.some(
    (draft) => draft.status === 'queued_outbox' || draft.status === 'publishing',
  );
}

export function useDrafts(reviewId: string | null) {
  const query = useQuery({
    queryKey: [...reviewDraftsQueryKey, reviewId],
    queryFn: ({ signal }) => {
      if (reviewId === null) {
        throw new Error('A review is required to fetch response drafts.');
      }
      return fetchReviewDrafts(reviewId, signal);
    },
    enabled: reviewId !== null,
    staleTime: 0,
    refetchInterval: (currentQuery) =>
      hasPendingPublication(currentQuery.state.data ?? [])
        ? TRANSIT_POLL_INTERVAL_MS
        : IDLE_POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
  });

  return {
    drafts: query.data ?? [],
    loading: query.isLoading,
    error: query.isError
      ? query.error instanceof Error
        ? query.error.message
        : 'Не удалось загрузить варианты ответа.'
      : null,
    retry: () => void query.refetch(),
  };
}
