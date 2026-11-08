import { useState, useMemo } from 'react';
import { useReviews } from '@/hooks/api/useReviews';
import { useArchiveReview } from '@/hooks/useArchiveReview';
import { ReviewCard } from './ReviewCard';
import { ReviewsFilterBar, type ReviewsFilters } from './ReviewsFilterBar';
import type { Review } from '@/api/services';

/**
 * ReviewsList — container component with filtering and skeleton loading
 *
 * Uses TanStack Query for data fetching and optimistic archive mutations
 */
export function ReviewsList() {
  const [filters, setFilters] = useState<ReviewsFilters>({
    search: '',
    replyStatus: 'all',
    sentiment: 'all',
    platform: 'all',
  });

  const { data, isLoading } = useReviews({ page: 1, page_size: 50 });
  const { mutate, isPending } = useArchiveReview();

  // Client-side filtering
  const filteredReviews = useMemo(() => {
    if (!data?.items) return [];

    return data.items.filter((review: Review) => {
      // Search filter
      if (filters.search && !review.text.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }

      // Reply status filter
      if (filters.replyStatus !== 'all') {
        if (filters.replyStatus === 'pending' && review.generated_reply) {
          return false;
        }
        if (filters.replyStatus === 'draft' && (!review.generated_reply || review.moderation_status === 'published')) {
          return false;
        }
        if (filters.replyStatus === 'published' && review.moderation_status !== 'published') {
          return false;
        }
      }

      // Sentiment filter
      if (filters.sentiment !== 'all' && review.sentiment !== filters.sentiment) {
        return false;
      }

      // Platform filter
      if (filters.platform !== 'all') {
        const platformMap: Record<string, string[]> = {
          yandex: ['yandex', 'yandex_maps'],
          '2gis': ['2gis', '2gis_maps'],
          google: ['google', 'google_business', 'google_maps'],
        };
        const platformAliases = platformMap[filters.platform] || [filters.platform];
        if (!review.platform || !platformAliases.some(alias => review.platform?.toLowerCase().includes(alias))) {
          return false;
        }
      }

      return true;
    });
  }, [data?.items, filters]);

  return (
    <>
      {/* Filter Bar */}
      <ReviewsFilterBar
        filters={filters}
        onFiltersChange={setFilters}
        totalCount={filteredReviews.length}
      />

      {/* Reviews List */}
      <div className="mt-4 space-y-4">
        {isLoading ? (
          // Loading Skeleton
          <>
            {Array.from({ length: 5 }).map((_, index) => (
              <div
                key={index}
                className="bg-white border border-slate-200 rounded-sm p-4"
              >
                {/* Skeleton Header */}
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex items-center gap-3">
                    <div className="h-3 w-20 bg-slate-200 rounded animate-pulse" />
                    <div className="h-3 w-24 bg-slate-200 rounded animate-pulse" />
                  </div>
                  <div className="h-5 w-20 bg-slate-200 rounded animate-pulse" />
                </div>

                {/* Skeleton Rating */}
                <div className="flex items-center gap-2 mb-3">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <div key={star} className="h-3 w-3 bg-slate-200 rounded animate-pulse" />
                    ))}
                  </div>
                </div>

                {/* Skeleton Text */}
                <div className="space-y-2 mb-4">
                  <div className="h-4 w-full bg-slate-200 rounded animate-pulse" />
                  <div className="h-4 w-5/6 bg-slate-200 rounded animate-pulse" />
                  <div className="h-4 w-4/6 bg-slate-200 rounded animate-pulse" />
                </div>

                {/* Skeleton Footer */}
                <div className="flex items-center justify-between pt-3 border-t border-slate-200">
                  <div className="h-3 w-32 bg-slate-200 rounded animate-pulse" />
                  <div className="h-8 w-20 bg-slate-200 rounded animate-pulse" />
                </div>
              </div>
            ))}
          </>
        ) : filteredReviews.length === 0 ? (
          // Empty State
          <div className="bg-white border border-slate-200 rounded-sm p-12 text-center shadow-sm">
            <div className="flex flex-col items-center max-w-md mx-auto">
              {/* Icon: Empty Box */}
              <svg
                className="w-16 h-16 text-slate-300 mb-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                />
              </svg>
              
              <h3 className="text-lg font-semibold text-slate-900 mb-2">
                Нет отзывов
              </h3>
              
              <p className="text-sm text-slate-500 leading-relaxed">
                Смягчите фильтры или подождите новых данных. Отзывы появятся здесь после импорта или добавления вручную.
              </p>
            </div>
          </div>
        ) : (
          // Reviews Cards
          <>
            {filteredReviews.map((review: Review) => (
              <ReviewCard
                key={review.id}
                review={review}
                onArchive={() => mutate({ reviewId: review.id })}
                isPending={isPending}
              />
            ))}
          </>
        )}
      </div>
    </>
  );
}
