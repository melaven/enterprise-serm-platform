import { useState } from 'react';
import { useSubmitReview, type SubmitReviewInput } from '@/hooks/useSubmitReview';

/**
 * ReviewForm — B2B form for manual review submission
 *
 * Design System: ink/chrome/plum/lime palette, no shadows, rounded-none
 * Features:
 * - Form validation
 * - Disabled state during submission
 * - Error handling
 * - Cancel button with AbortController
 */
export function ReviewForm({ onSuccess }: { onSuccess?: () => void }) {
  const [formData, setFormData] = useState<SubmitReviewInput>({
    platform: '',
    author_name: '',
    rating: 5,
    text: '',
    tags: [],
  });

  const [ratingHover, setRatingHover] = useState(0);

  const { mutate, isPending, isError, error, cancel } = useSubmitReview({
    onSuccess: () => {
      // Reset form on success
      setFormData({
        platform: '',
        author_name: '',
        rating: 5,
        text: '',
        tags: [],
      });
      onSuccess?.();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Basic validation
    if (!formData.platform.trim()) {
      return;
    }
    if (!formData.text.trim()) {
      return;
    }
    if (formData.rating < 1 || formData.rating > 5) {
      return;
    }

    mutate(formData);
  };

  const handleCancel = () => {
    if (isPending) {
      cancel();
    } else {
      // Reset form if not submitting
      setFormData({
        platform: '',
        author_name: '',
        rating: 5,
        text: '',
        tags: [],
      });
    }
  };

  const isFormDisabled = isPending;

  return (
    <div className="bg-ink-50 border border-chrome-600 rounded-none p-6">
      <div className="mb-6">
        <h3 className="text-xl font-semibold text-chrome-300 mb-2">
          Добавить отзыв вручную
        </h3>
        <p className="text-sm text-chrome-500">
          Введите данные отзыва для добавления в систему
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Platform */}
        <div>
          <label className="block text-xs font-medium text-chrome-400 uppercase tracking-wider mb-2">
            Платформа *
          </label>
          <input
            type="text"
            value={formData.platform}
            onChange={(e) => setFormData({ ...formData, platform: e.target.value })}
            disabled={isFormDisabled}
            placeholder="Например: Google, Yandex, TripAdvisor"
            className="
              w-full
              bg-ink-800
              text-chrome-300 placeholder:text-chrome-500
              border border-chrome-600 focus:border-plum
              rounded-none
              px-3 py-2
              text-sm
              outline-none
              transition-colors duration-150
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          />
        </div>

        {/* Author Name */}
        <div>
          <label className="block text-xs font-medium text-chrome-400 uppercase tracking-wider mb-2">
            Имя автора
          </label>
          <input
            type="text"
            value={formData.author_name}
            onChange={(e) => setFormData({ ...formData, author_name: e.target.value })}
            disabled={isFormDisabled}
            placeholder="Имя клиента (опционально)"
            className="
              w-full
              bg-ink-800
              text-chrome-300 placeholder:text-chrome-500
              border border-chrome-600 focus:border-plum
              rounded-none
              px-3 py-2
              text-sm
              outline-none
              transition-colors duration-150
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          />
        </div>

        {/* Rating */}
        <div>
          <label className="block text-xs font-medium text-chrome-400 uppercase tracking-wider mb-2">
            Рейтинг *
          </label>
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setFormData({ ...formData, rating: star })}
                  onMouseEnter={() => setRatingHover(star)}
                  onMouseLeave={() => setRatingHover(0)}
                  disabled={isFormDisabled}
                  className={`
                    text-lg
                    transition-colors duration-150
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${
                      star <= (ratingHover || formData.rating)
                        ? 'text-lime'
                        : 'text-chrome-700'
                    }
                  `}
                >
                  ★
                </button>
              ))}
            </div>
            <span className="text-sm text-chrome-500">
              {formData.rating}/5
            </span>
          </div>
        </div>

        {/* Review Text */}
        <div>
          <label className="block text-xs font-medium text-chrome-400 uppercase tracking-wider mb-2">
            Текст отзыва *
          </label>
          <textarea
            value={formData.text}
            onChange={(e) => setFormData({ ...formData, text: e.target.value })}
            disabled={isFormDisabled}
            placeholder="Введите текст отзыва..."
            rows={4}
            className="
              w-full
              bg-ink-800
              text-chrome-300 placeholder:text-chrome-500
              border border-chrome-600 focus:border-plum
              rounded-none
              px-3 py-2
              text-sm
              outline-none
              resize-none
              transition-colors duration-150
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          />
        </div>

        {/* Error Message */}
        {isError && (
          <div className="bg-plum-900 border-2 border-plum-700 rounded-sm px-4 py-3">
            <p className="text-sm font-medium text-plum-300">
              {error?.message || 'Не удалось добавить отзыв. Попробуйте снова.'}
            </p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-chrome-600/50">
          <button
            type="button"
            onClick={handleCancel}
            disabled={isFormDisabled}
            className="
              bg-transparent hover:bg-ink-800
              text-chrome-300 hover:text-white
              font-medium text-sm
              px-4 py-2
              border-2 border-chrome-600 hover:border-chrome-400
              rounded-none
              transition-colors duration-150
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            {isPending ? 'Отмена...' : 'Отмена'}
          </button>
          <button
            type="submit"
            disabled={isFormDisabled || !formData.platform.trim() || !formData.text.trim()}
            className="
              bg-plum hover:bg-plum-400 active:bg-plum-600
              text-white font-medium text-sm
              px-4 py-2
              border-2 border-transparent
              rounded-none
              transition-colors duration-150
              disabled:opacity-50 disabled:cursor-not-allowed
            "
          >
            {isPending ? 'Отправка...' : 'Добавить отзыв'}
          </button>
        </div>
      </form>
    </div>
  );
}
