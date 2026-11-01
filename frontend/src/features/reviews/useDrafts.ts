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
    setState((current) => ({
      reviewId,
      drafts: current.reviewId === reviewId ? current.drafts : [],
      loading: true,
      error: null,
    }));

    const refresh = async (initial = false): Promise<void> => {
      if ((!initial && document.visibilityState !== 'visible') || inFlight) return;
      inFlight = true;
      try {
        const drafts = await fetchReviewDrafts(reviewId, controller.signal);
        if (active) setState({ reviewId, drafts, loading: false, error: null });
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
      }
    };

    void refresh(true);
    const intervalId = window.setInterval(() => void refresh(), 15_000);
    const handleVisibilityChange = (): void => {
      if (document.visibilityState === 'visible') void refresh();
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      active = false;
      controller.abort();
      window.clearInterval(intervalId);
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
