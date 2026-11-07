import type { Review } from '@/api/services';

interface ReviewCardProps {
  review: Review;
  onArchive: () => void;
  isPending?: boolean;
}

/**
 * ReviewCard — minimalist B2B review display component
 *
 * Design System: ink/chrome/plum/lime palette, no shadows, ≤2px rounded
 */
export function ReviewCard({ review, onArchive, isPending = false }: ReviewCardProps) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  };

  const getSentimentColor = (sentiment: Review['sentiment']) => {
    switch (sentiment) {
      case 'POSITIVE':
        return 'bg-lime-900 text-lime border-lime-700';
      case 'NEGATIVE':
        return 'bg-plum-900 text-plum-300 border-plum-700';
      case 'NEUTRAL':
        return 'bg-ink-800 text-chrome-400 border-chrome-600';
      default:
        return 'bg-ink-800 text-chrome-500 border-chrome-600';
    }
  };

  return (
    <div className="bg-ink-50 border border-chrome-600 rounded-none p-4">
      {/* Header: Platform, Date, Sentiment */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-chrome-500 uppercase tracking-wider">
            {review.platform || 'Unknown'}
          </span>
          <span className="text-xs text-chrome-500">
            {formatDate(review.created_at)}
          </span>
        </div>
        <span
          className={`
            inline-flex items-center
            px-2 py-0.5
            border
            rounded-sm
            text-xs font-medium
            ${getSentimentColor(review.sentiment)}
          `}
        >
          {review.sentiment || 'UNCLASSIFIED'}
        </span>
      </div>

      {/* Rating */}
      <div className="flex items-center gap-2 mb-3">
        <div className="flex">
          {[1, 2, 3, 4, 5].map((star) => (
            <span
              key={star}
              className={`text-sm ${
                star <= review.rating ? 'text-lime' : 'text-chrome-700'
              }`}
            >
              ★
            </span>
          ))}
        </div>
        <span className="text-sm text-chrome-500">
          {review.rating}/5
        </span>
      </div>

      {/* Review Text */}
      <p className="text-sm text-chrome-300 mb-4 leading-relaxed">
        {review.text}
      </p>

      {/* AI-Generated Reply Block */}
      {review.generated_reply && (
        <div className="mt-4 p-4 bg-slate-50 border-l-2 border-slate-400 rounded-r-md">
          <div className="flex items-center gap-1.5 mb-2">
            <svg
              className="w-3 h-3 text-slate-500"
              fill="currentColor"
              viewBox="0 0 20 20"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            <span className="text-xs text-slate-500 uppercase font-semibold tracking-wide">
              SentiGuard AI Draft
            </span>
          </div>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">
            {review.generated_reply}
          </p>
        </div>
      )}

      {/* Footer: Author & Archive Button */}
      <div className="flex items-center justify-between pt-3 border-t border-chrome-600/50">
        {review.author_name && (
          <span className="text-xs text-chrome-500">
            {review.author_name}
          </span>
        )}
        <button
          onClick={onArchive}
          disabled={isPending}
          className={`
            font-medium text-sm
            px-3 py-1.5
            border
            rounded-sm
            transition-colors duration-150
            ${
              isPending
                ? 'bg-transparent text-chrome-700 border-chrome-700 cursor-not-allowed opacity-50'
                : 'bg-transparent text-red-400 border-red-700/50 hover:text-red-300 hover:bg-ink-800 hover:border-red-600'
            }
          `}
        >
          {isPending ? 'Архивация...' : 'В архив'}
        </button>
      </div>
    </div>
  );
}
