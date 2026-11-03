import { act, renderHook } from '@testing-library/react';
import { createElement, type PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchReviewDrafts, type DraftResponse } from './draftsApi';
import { useDrafts } from './useDrafts';

vi.mock('./draftsApi', () => ({
  fetchReviewDrafts: vi.fn(),
}));

const draft = (status: DraftResponse['status']): DraftResponse =>
  ({
    id: 'draft-1',
    strategy: 'LEGAL_STRICT',
    body: 'Reply',
    is_approved: status !== null,
    approved_by: null,
    approved_at: null,
    created_at: '',
    updated_at: '',
    status,
    external_reply_id: null,
    failure_reason: null,
  }) satisfies DraftResponse;

function createQueryClientWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });

  return function QueryClientWrapper({ children }: PropsWithChildren) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe('useDrafts polling', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  it('polls quickly during publication and returns to idle polling when terminal', async () => {
    vi.mocked(fetchReviewDrafts)
      .mockResolvedValueOnce([draft('queued_outbox')])
      .mockResolvedValueOnce([draft('publishing')])
      .mockResolvedValueOnce([draft('published')])
      .mockResolvedValue([draft('published')]);

    const { unmount } = renderHook(() => useDrafts('review-1'), {
      wrapper: createQueryClientWrapper(),
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3_999);
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(19_999);
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(4);
    unmount();
  });

  it('does not request until a review is selected', async () => {
    vi.mocked(fetchReviewDrafts).mockResolvedValue([]);

    const { result, rerender, unmount } = renderHook(
      ({ reviewId }) => useDrafts(reviewId),
      {
        initialProps: { reviewId: null as string | null },
        wrapper: createQueryClientWrapper(),
      },
    );
    expect(fetchReviewDrafts).not.toHaveBeenCalled();

    rerender({ reviewId: 'review-1' });
    await act(async () => {
      await Promise.resolve();
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(1);
    expect(result.current.drafts).toEqual([]);
    unmount();
  });
});
