import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchReviews: vi.fn(),
  fetchReviewDrafts: vi.fn(),
  retryReplyPublication: vi.fn(),
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
  retryReplyPublication: mocks.retryReplyPublication,
}));

vi.mock('./approveDraftApi', () => ({
  approveDraft: mocks.approveDraft,
}));

vi.mock('@/store/useAppStore', () => ({
  useAppStore: (selector: (state: { user: { tenant_id: string } }) => unknown) =>
    selector({ user: { tenant_id: 'tenant-1' } }),
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
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ReviewsDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function setVisibilityState(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: state });
}

describe('ReviewsDashboard reply generation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setVisibilityState('visible');
    mocks.token = null;
    mocks.fetchReviews.mockResolvedValue([review]);
    mocks.fetchReviewDrafts.mockResolvedValue([]);
    mocks.retryReplyPublication.mockResolvedValue(undefined);
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
        status: null,
        external_reply_id: null,
        failure_reason: null,
        approved_by: null,
        approved_at: null,
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
        status: null,
        external_reply_id: null,
        failure_reason: null,
        approved_by: null,
        approved_at: null,
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

  it('polls reviews only while visible and discovers newly critical reviews', async () => {
    mocks.fetchReviews
      .mockResolvedValueOnce([review])
      .mockResolvedValueOnce([{ ...review, risk_level: 'critical_risk' }]);

    renderDashboard();
    expect(await screen.findByRole('button', { name: /Review author/ })).toBeInTheDocument();

    setVisibilityState('hidden');
    fireEvent(window, new Event('visibilitychange'));
    expect(mocks.fetchReviews).toHaveBeenCalledTimes(1);

    setVisibilityState('visible');
    fireEvent(window, new Event('visibilitychange'));
    expect(await screen.findByText('Перехвачен отзыв с риском CRITICAL_RISK')).toBeInTheDocument();
    expect(await screen.findByText('Критический риск')).toBeInTheDocument();
    expect(mocks.fetchReviews).toHaveBeenCalledTimes(2);
  });

  it('synchronizes approved drafts in the background without replacing active edits', async () => {
    const payload = window.btoa(JSON.stringify({ company_role: 'admin' }));
    mocks.token = `header.${payload}.signature`;
    mocks.fetchReviews.mockResolvedValue([{ ...review, risk_level: 'critical_risk' }]);
    let anotherManagerApproved = false;
    const currentDrafts = [
      {
        id: 'draft-1',
        strategy: 'LEGAL_STRICT' as const,
        body: 'Server response draft',
        is_approved: false,
        status: null,
        external_reply_id: null,
        failure_reason: null,
        approved_by: null,
        approved_at: null,
        created_at: '2026-10-30T00:00:00Z',
        updated_at: '2026-10-30T00:00:00Z',
      },
    ];
    const approvedDrafts = [
      {
        ...currentDrafts[0],
        is_approved: true,
        status: 'queued_outbox' as const,
        approved_by: 'colleague@example.com',
        approved_at: '2026-11-02T00:00:00Z',
        updated_at: '2026-11-02T00:00:00Z',
      },
    ];
    mocks.fetchReviewDrafts.mockImplementation(() =>
      Promise.resolve(anotherManagerApproved ? approvedDrafts : currentDrafts),
    );

    renderDashboard();
    fireEvent.click(await screen.findByRole('button', { name: 'Редактировать: Юридически строгий' }));
    const editor = await screen.findByRole('textbox', { name: 'Текст ответа: Юридически строгий' });
    fireEvent.change(editor, { target: { value: 'Local unsaved changes' } });

    setVisibilityState('hidden');
    fireEvent(window, new Event('visibilitychange'));
    const requestsBeforeVisible = mocks.fetchReviewDrafts.mock.calls.length;

    setVisibilityState('visible');
    anotherManagerApproved = true;
    fireEvent(window, new Event('visibilitychange'));
    expect(await screen.findByText(/colleague@example\.com.*уже отправил ответ/)).toBeInTheDocument();
    expect(await screen.findByRole('textbox', { name: 'Текст ответа: Юридически строгий' })).toHaveValue(
      'Local unsaved changes',
    );
    expect(
      screen.queryByRole('button', { name: 'Апрув и Отправка (Approve & Send): Юридически строгий' }),
    ).not.toBeInTheDocument();
    expect(mocks.fetchReviewDrafts).toHaveBeenCalledTimes(requestsBeforeVisible + 1);
  });

  it('renders publication states and offers a retry for a failed publication', async () => {
    const payload = window.btoa(JSON.stringify({ company_role: 'admin' }));
    mocks.token = `header.${payload}.signature`;
    mocks.fetchReviews.mockResolvedValue([{ ...review, risk_level: 'CRITICAL_RISK' }]);
    let publicationStatus: 'queued_outbox' | 'publish_failed' = 'publish_failed';
    const draft = {
      id: 'draft-1',
      strategy: 'LEGAL_STRICT' as const,
      body: 'Approved response',
      is_approved: true,
      status: publicationStatus,
      external_reply_id: null,
      failure_reason: 'Токен доступа истёк или недействителен.',
      approved_by: 'admin',
      approved_at: '2026-11-02T00:00:00Z',
      created_at: '2026-10-30T00:00:00Z',
      updated_at: '2026-11-02T00:00:00Z',
    };
    mocks.fetchReviewDrafts.mockImplementation(() =>
      Promise.resolve([{ ...draft, status: publicationStatus }]),
    );
    mocks.retryReplyPublication.mockImplementation(async () => {
      publicationStatus = 'queued_outbox';
    });

    renderDashboard();
    expect(await screen.findByText(/🔴 Ошибка: Токен доступа истёк/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Апрув и Отправка/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Повторить' })).toBeEnabled();

    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));

    await waitFor(() => {
      expect(mocks.retryReplyPublication).toHaveBeenCalledWith('review-1', 'draft-1');
      expect(screen.getByText('🟡 В очереди на отправку')).toBeInTheDocument();
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith('Публикация повторно поставлена в очередь');
  });
});
