import { act, renderHook } from '@testing-library/react';
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

function setVisibilityState(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    value: state,
  });
}

describe('useDrafts polling', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    setVisibilityState('visible');
  });

  it('polls quickly during publication and returns to idle polling when terminal', async () => {
    vi.mocked(fetchReviewDrafts)
      .mockResolvedValueOnce([draft('queued_outbox')])
      .mockResolvedValueOnce([draft('publishing')])
      .mockResolvedValueOnce([draft('published')])
      .mockResolvedValue([draft('published')]);

    const { unmount } = renderHook(() => useDrafts('review-1'));
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

  it('does not request while hidden and refreshes when visible', async () => {
    setVisibilityState('hidden');
    vi.mocked(fetchReviewDrafts).mockResolvedValue([]);

    const { unmount } = renderHook(() => useDrafts('review-1'));
    expect(fetchReviewDrafts).not.toHaveBeenCalled();

    setVisibilityState('visible');
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'));
      await Promise.resolve();
    });
    expect(fetchReviewDrafts).toHaveBeenCalledTimes(1);
    unmount();
  });
});
