import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock('@/api/services', () => ({
  apiClient: { post: mocks.post },
}));

import { approveDraft } from './approveDraftApi';

describe('approveDraft API', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends the backend request shape and adapts its response', async () => {
    mocks.post.mockResolvedValue({
      status: 200,
      data: {
        draft: { id: 'draft-1', is_approved: true },
        idempotent: false,
        publication_status: 'outbox_pending',
        approved_by: null,
        approved_at: null,
      },
    });

    await expect(
      approveDraft({ reviewId: 'review-1', draftId: 'draft-1', content: 'Edited response' }),
    ).resolves.toEqual({
      approved_draft_id: 'draft-1',
      status: 'approved',
      outbox_queued: true,
      approved_by: null,
      approved_at: null,
    });

    const [url, body, config] = mocks.post.mock.calls[0] as [
      string,
      { edited_text: string },
      { validateStatus: (status: number) => boolean },
    ];
    expect(url).toBe('/v1/reviews/review-1/drafts/draft-1/approve');
    expect(body).toEqual({ edited_text: 'Edited response' });
    expect(config.validateStatus(409)).toBe(true);
    expect(config.validateStatus(401)).toBe(false);
  });
});
