import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchReviews: vi.fn(),
  generateReviewReply: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock('@/api/reviews', () => ({
  fetchReviews: mocks.fetchReviews,
  generateReviewReply: mocks.generateReviewReply,
}));

vi.mock('@/store/useAppStore', () => ({
  useAuth: () => ({ user: { tenant_id: 'tenant-1' } }),
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
    mocks.fetchReviews.mockResolvedValue([review]);
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
});
