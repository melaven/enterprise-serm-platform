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
    setState({ reviewId, drafts: [], loading: true, error: null });
    void fetchReviewDrafts(reviewId, controller.signal)
      .then((drafts) => {
        setState({ reviewId, drafts, loading: false, error: null });
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          reviewId,
          drafts: [],
          loading: false,
          error: cause instanceof Error ? cause.message : 'Не удалось загрузить варианты ответа.',
        });
      });

    return () => controller.abort();
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
