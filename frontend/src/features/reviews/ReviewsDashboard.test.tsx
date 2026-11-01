import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchReviews: vi.fn(),
  fetchReviewDrafts: vi.fn(),
  generateReviewReply: vi.fn(),
  approveDraft: vi.fn(),
  token: null as string | null,
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('@/api/reviews', () => ({
  fetchReviews: mocks.fetchReviews,
  generateReviewReply: mocks.generateReviewReply,
}));

vi.mock('./draftsApi', () => ({
  fetchReviewDrafts: mocks.fetchReviewDrafts,
}));

vi.mock('./approveDraftApi', () => ({
  approveDraft: mocks.approveDraft,
}));

vi.mock('@/store/useAppStore', () => ({
  useAuth: () => ({ user: { tenant_id: 'tenant-1' }, token: mocks.token }),
}));

vi.mock('sonner', () => ({
  toast: {
    error: mocks.toastError,
    success: mocks.toastSuccess,
  },
}));

import { ReviewsDashboard } from './ReviewsDashboard';

const review = {
  id: 'review-1',
  company_id: 'tenant-1',
  platform: 'yandex',
  author_hash: 'author-hash',
  author_display: 'Review author',
  text: 'Review text',
  rating: 4,
  published_at: '2026-10-29T18:42:00Z',
  risk_level: 'safe',
};

function renderDashboard() {
  return render(
    <MemoryRouter>
      <ReviewsDashboard />
    </MemoryRouter>,
  );
}

describe('ReviewsDashboard reply generation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.token = null;
    mocks.fetchReviews.mockResolvedValue([review]);
    mocks.fetchReviewDrafts.mockResolvedValue([]);
  });

  it('shows a blocking loader and displays the generated reply only after success', async () => {
    let resolveReply!: (reply: string) => void;
    mocks.generateReviewReply.mockReturnValue(
      new Promise<string>((resolve) => {
        resolveReply = resolve;
      }),
    );

    renderDashboard();

    const button = await screen.findByRole('button', { name: 'Ответить с помощью AI' });
    fireEvent.click(button);

    expect(button).toBeDisabled();
    expect(await screen.findByRole('button', { name: 'Генерируем ответ…' })).toBeDisabled();
    expect(screen.queryByText('Generated reply')).not.toBeInTheDocument();

    resolveReply('Generated reply');

    expect(await screen.findByText('Generated reply')).toBeInTheDocument();
    await waitFor(() => expect(button).toBeEnabled());
  });

  it('keeps the original UI and reports an error when generation fails', async () => {
    mocks.generateReviewReply.mockRejectedValue(new Error('Payment required'));

    renderDashboard();

    const button = await screen.findByRole('button', { name: 'Ответить с помощью AI' });
    fireEvent.click(button);

    await waitFor(() => expect(button).toBeEnabled());
    expect(screen.queryByText('Generated reply')).not.toBeInTheDocument();
    expect(mocks.toastError).toHaveBeenCalledWith('Не удалось сгенерировать ответ', {
      description: 'Payment required',
    });
  });

  it('loads real crisis drafts for a critical review and uses read-only RBAC without a role claim', async () => {
    mocks.fetchReviews.mockResolvedValue([{ ...review, risk_level: 'critical_risk' }]);
    mocks.fetchReviewDrafts.mockResolvedValue([
      {
        id: 'draft-1',
        strategy: 'LEGAL_STRICT',
        body: 'Backend draft text',
        is_approved: false,
        created_at: '2026-10-30T00:00:00Z',
        updated_at: '2026-10-30T00:00:00Z',
      },
    ]);

    renderDashboard();

    expect(await screen.findByText('Перехвачен отзыв с риском CRITICAL_RISK')).toBeInTheDocument();
    expect(await screen.findByText('Backend draft text')).toBeInTheDocument();
    expect(mocks.fetchReviewDrafts).toHaveBeenCalledWith('review-1', expect.any(AbortSignal));
    expect(screen.getByText(/Режим просмотра/)).toBeInTheDocument();
  });

  it('waits for approval, disables the action, and preserves the draft after failure', async () => {
    const payload = window.btoa(JSON.stringify({ company_role: 'admin' }));
    mocks.token = `header.${payload}.signature`;
    mocks.fetchReviews.mockResolvedValue([{ ...review, risk_level: 'CRITICAL_RISK' }]);
    mocks.fetchReviewDrafts.mockResolvedValue([
      {
        id: 'draft-1',
        strategy: 'LEGAL_STRICT',
        body: 'Keep this draft unchanged',
        is_approved: false,
        created_at: '2026-10-30T00:00:00Z',
        updated_at: '2026-10-30T00:00:00Z',
      },
    ]);

    let rejectApproval!: (error: Error) => void;
    mocks.approveDraft.mockReturnValue(
      new Promise((_, reject) => {
        rejectApproval = reject;
      }),
    );
    renderDashboard();

    const approveButton = await screen.findByRole('button', {
      name: 'Апрув и Отправка (Approve & Send): Юридически строгий',
    });
    fireEvent.click(approveButton);
    fireEvent.click(await screen.findByRole('button', { name: 'Подтвердить' }));

    await waitFor(() => expect(mocks.approveDraft).toHaveBeenCalledWith({
      reviewId: 'review-1',
      draftId: 'draft-1',
      content: 'Keep this draft unchanged',
    }));
    expect(await screen.findByRole('button', { name: 'Апрув и Отправка (Approve & Send): Юридически строгий' })).toBeDisabled();
    expect(screen.queryByText('Ответ отправлен в Outbox')).not.toBeInTheDocument();

    rejectApproval(new Error('Network failed'));

    expect(await screen.findByText('Ошибка сервера. Ответ не отправлен, повторите попытку.')).toBeInTheDocument();
    expect(screen.getByText('Keep this draft unchanged')).toBeInTheDocument();
    expect(mocks.toastError).toHaveBeenCalledWith('Не удалось подтвердить ответ', {
      description: 'Попробуйте ещё раз.',
    });
  });
});
