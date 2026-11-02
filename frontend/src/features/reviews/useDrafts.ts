import { useCallback, useEffect, useState } from 'react';

import { fetchReviewDrafts, type DraftResponse } from './draftsApi';

interface DraftsState {
  readonly reviewId: string | null;
  readonly drafts: readonly DraftResponse[];
  readonly loading: boolean;
  readonly error: string | null;
}

const EMPTY_STATE: DraftsState = {
  reviewId: null,
  drafts: [],
  loading: false,
  error: null,
};

const TRANSIT_POLL_INTERVAL_MS = 4_000;
const IDLE_POLL_INTERVAL_MS = 20_000;

function hasPendingPublication(drafts: readonly DraftResponse[]): boolean {
  return drafts.some(
    (draft) => draft.status === 'queued_outbox' || draft.status === 'publishing',
  );
}

export function useDrafts(reviewId: string | null) {
  const [state, setState] = useState<DraftsState>(EMPTY_STATE);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (reviewId === null) {
      setState(EMPTY_STATE);
      return;
    }

    const controller = new AbortController();
    let active = true;
    let inFlight = false;
    let pollingTimeout: number | undefined;
    let currentDrafts: readonly DraftResponse[] = [];
    setState((current) => ({
      reviewId,
      drafts: current.reviewId === reviewId ? current.drafts : [],
      loading: true,
      error: null,
    }));

    const scheduleNextPoll = (): void => {
      if (!active || document.visibilityState !== 'visible') return;
      window.clearTimeout(pollingTimeout);
      const interval = hasPendingPublication(currentDrafts)
        ? TRANSIT_POLL_INTERVAL_MS
        : IDLE_POLL_INTERVAL_MS;
      pollingTimeout = window.setTimeout(() => void refresh(), interval);
    };

    const refresh = async (): Promise<void> => {
      if (document.visibilityState !== 'visible' || inFlight) return;
      inFlight = true;
      try {
        const drafts = await fetchReviewDrafts(reviewId, controller.signal);
        if (active) {
          currentDrafts = drafts;
          setState({ reviewId, drafts, loading: false, error: null });
        }
      } catch (cause: unknown) {
        if (!active || controller.signal.aborted) return;
        setState((current) => ({
          reviewId,
          drafts: current.reviewId === reviewId ? current.drafts : [],
          loading: false,
          error: cause instanceof Error ? cause.message : 'Не удалось загрузить варианты ответа.',
        }));
      } finally {
        inFlight = false;
        scheduleNextPoll();
      }
    };

    void refresh();
    const handleVisibilityChange = (): void => {
      if (document.visibilityState === 'visible') {
        void refresh();
      } else {
        window.clearTimeout(pollingTimeout);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(pollingTimeout);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [reviewId, revision]);

  const retry = useCallback(() => setRevision((current) => current + 1), []);

  if (state.reviewId !== reviewId) {
    return {
      drafts: [] as readonly DraftResponse[],
      loading: reviewId !== null,
      error: null,
      retry,
    };
  }

  return { drafts: state.drafts, loading: state.loading, error: state.error, retry };
}
