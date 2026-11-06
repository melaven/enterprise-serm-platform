import { useReviews } from '@/hooks/api/useReviews';
import { useArchiveReview } from '@/hooks/useArchiveReview';
import { ReviewCard } from './ReviewCard';

/**
 * ReviewsList — container component with skeleton loading
 *
 * Uses TanStack Query for data fetching and optimistic archive mutations
 */
export function ReviewsList() {
  const { data, isLoading } = useReviews({ page: 1, page_size: 50 });
  const { mutate, isPending } = useArchiveReview();

  // Loading Skeleton
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            key={index}
            className="bg-ink-50 border border-chrome-600 rounded-none p-4 animate-pulse"
          >
            {/* Skeleton Header */}
            <div className="flex items-start justify-between gap-4 mb-3">
              <div className="flex items-center gap-3">
                <div className="h-4 w-20 bg-ink-800 rounded-sm" />
                <div className="h-4 w-24 bg-ink-800 rounded-sm" />
              </div>
              <div className="h-6 w-16 bg-ink-800 rounded-sm" />
            </div>

            {/* Skeleton Rating */}
            <div className="flex items-center gap-2 mb-3">
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <div key={star} className="h-4 w-4 bg-ink-800 rounded-sm" />
                ))}
              </div>
              <div className="h-4 w-12 bg-ink-800 rounded-sm" />
            </div>

            {/* Skeleton Text */}
            <div className="space-y-2 mb-4">
              <div className="h-4 w-full bg-ink-800 rounded-sm" />
              <div className="h-4 w-5/6 bg-ink-800 rounded-sm" />
              <div className="h-4 w-4/6 bg-ink-800 rounded-sm" />
            </div>

            {/* Skeleton Footer */}
            <div className="flex items-center justify-between pt-3 border-t border-chrome-600/50">
              <div className="h-4 w-32 bg-ink-800 rounded-sm" />
              <div className="h-8 w-20 bg-ink-800 rounded-sm" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!data?.items || data.items.length === 0) {
    return (
      <div className="bg-ink-50 border border-chrome-600 rounded-none p-8 text-center">
        <p className="text-sm text-chrome-400">
          Нет отзывов для отображения
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {data.items.map((review) => (
        <ReviewCard
          key={review.id}
          review={review}
          onArchive={() => mutate({ reviewId: review.id })}
          isPending={isPending}
        />
      ))}
    </div>
  );
}
