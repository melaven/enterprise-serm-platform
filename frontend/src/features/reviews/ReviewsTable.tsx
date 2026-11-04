import { useMemo, useRef, useState } from 'react';
import { Database, Download } from 'lucide-react';
import { ErrorBoundary } from 'react-error-boundary';
import { useVirtualizer } from '@tanstack/react-virtual';

import {
  Table,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { Review } from '../../api/services';
import { ReviewDetailModal } from './ReviewDetailModal';
import { ErrorFallback } from '@/components/ui/ErrorFallback';
import { useReviews } from '@/hooks/api/useReviews';

/**
 * Таблица отзывов
 * Загружает данные через TanStack Query.
 */
export interface ReviewsTableProps {
  searchQuery?: string;
  sentimentFilter?: string;
  platformFilter?: string;
  onExportCSV?: () => void;
}

function ReviewsTableContent({
  searchQuery,
  sentimentFilter,
  platformFilter,
  onExportCSV,
}: ReviewsTableProps) {
  const params = useMemo(
    () => ({
      page_size: 50,
      ...(platformFilter && platformFilter !== 'all' ? { platform: platformFilter } : {}),
      ...(sentimentFilter && sentimentFilter !== 'all' ? { sentiment: sentimentFilter } : {}),
      ...(searchQuery?.trim() ? { search: searchQuery.trim() } : {}),
    }),
    [platformFilter, searchQuery, sentimentFilter],
  );
  const reviewsQuery = useReviews(params);
  const reviews = reviewsQuery.data?.items ?? [];
  const reviewsTotal = reviewsQuery.data?.total ?? 0;
  const [selectedReview, setSelectedReview] = useState<Review | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Ref for the scrollable parent container
  const tableContainerRef = useRef<HTMLDivElement>(null);

  const handleRowClick = (review: Review) => {
    setSelectedReview(review);
    setIsModalOpen(true);
  };

  // Фильтрация по поисковому запросу (клиентская фильтрация)
  const filteredReviews = searchQuery
    ? reviews.filter((review) =>
        review.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
      review.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : reviews;

  // Initialize virtualizer
  const rowVirtualizer = useVirtualizer({
    count: filteredReviews.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => 60, // Estimated height of each row
    overscan: 5, // Render a few extra items for smooth scrolling
  });

  const getSentimentBadge = (sentiment: string | null) => {
    if (!sentiment) return <Badge variant="secondary">Не определена</Badge>;

    switch (sentiment) {
      case 'POSITIVE':
        return <Badge variant="success">Позитивный</Badge>;
      case 'NEGATIVE':
        return <Badge variant="destructive">Негативный</Badge>;
      case 'NEUTRAL':
        return <Badge variant="secondary">Нейтральный</Badge>;
      case 'UNCLASSIFIED':
        return <Badge variant="outline">Не классифицирован</Badge>;
      default:
        return <Badge variant="outline">{sentiment}</Badge>;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderStars = (rating: number) => {
    return '★'.repeat(Math.min(rating, 5)) + '☆'.repeat(Math.max(5 - rating, 0));
  };

  // Loading Skeleton
  if (reviewsQuery.isLoading) {
    return (
      <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-6">
        <div className="space-y-4">
          <Skeleton className="h-6 w-1/4" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-3/4" />
        </div>
      </div>
    );
  }

  if (reviewsQuery.isError && reviewsQuery.data === undefined) {
    return (
      <div role="alert" className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-6 text-chrome-200">
        <p>Не удалось загрузить отзывы: {reviewsQuery.error.message}</p>
        <Button className="mt-4" variant="outline" onClick={() => void reviewsQuery.refetch()}>
          Повторить
        </Button>
      </div>
    );
  }

  // Empty State
  if (filteredReviews.length === 0) {
    const isSearching = searchQuery || sentimentFilter !== 'all' || platformFilter !== 'all';
    
    return (
      <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-white">
              Отзывы
            </h3>
            <p className="text-sm text-chrome-400 mt-1">
              {isSearching ? 'Ничего не найдено' : 'Отзывы не найдены'}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => void reviewsQuery.refetch()}
          >
            Обновить
          </Button>
        </div>

        {/* Empty State */}
        <div className="border-2 border-chrome-600 rounded-sm bg-ink-950 p-12 text-center flex flex-col items-center justify-center">
          <Database className="w-12 h-12 text-chrome-600 mb-4" strokeWidth={1.25} />
          <h3 className="text-white font-medium mb-1">
            {isSearching ? 'Нет результатов' : 'Нет отзывов'}
          </h3>
          <p className="text-chrome-400 text-sm max-w-sm mb-4">
            {isSearching 
              ? 'Попробуйте изменить параметры фильтрации или сбросить фильтры'
              : 'Данные появятся после импорта клиента или синхронизации официальной интеграции.'
            }
          </p>
          
          {/* Contextual Action Button */}
          {isSearching ? (
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => {
                window.location.href = '/reviews';
              }}
            >
              Сбросить все фильтры
            </Button>
          ) : (
            <Button 
              variant="accent" 
              size="sm"
              onClick={() => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            >
              Обновить
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-white">
              Отзывы
            </h3>
            <p className="text-sm text-chrome-400 mt-1">
              {searchQuery 
                ? `Найдено ${filteredReviews.length} из ${reviewsTotal} отзывов`
                : `Всего ${reviewsTotal} отзывов`
              }
            </p>
          </div>
          <div className="flex items-center gap-2">
            {onExportCSV && (
              <Button variant="outline" onClick={onExportCSV}>
                <Download className="h-4 w-4 mr-2" />
                Экспорт CSV
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => void reviewsQuery.refetch()}
            >
              Обновить
            </Button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Платформа</TableHead>
                <TableHead>Рейтинг</TableHead>
                <TableHead>Сводка SI</TableHead>
                <TableHead>Тональность</TableHead>
                <TableHead>Уровень угрозы</TableHead>
                <TableHead>Теги</TableHead>
                <TableHead>Дата</TableHead>
              </TableRow>
            </TableHeader>
          </Table>
          <div
            ref={tableContainerRef}
            className="overflow-y-auto max-h-[600px]"
          >
            <div
              style={{
                height: `${rowVirtualizer.getTotalSize()}px`,
                width: '100%',
                position: 'relative',
              }}
            >
              {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                const review = filteredReviews[virtualRow.index];
                return (
                  <div
                    key={review.id}
                    data-index={virtualRow.index}
                    ref={(el) => rowVirtualizer.measureElement(el)}
                    className="grid grid-cols-7 gap-4 px-4 py-3 border-b border-chrome-600/50 hover:bg-ink-50 transition-colors cursor-pointer absolute left-0 top-0 w-full items-center"
                    style={{
                      height: `${virtualRow.size}px`,
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                    onClick={() => handleRowClick(review)}
                  >
                    <div className="font-medium text-sm text-chrome-300">
                      {review.platform}
                    </div>
                    <div>
                      <span className="text-lime font-mono text-sm">
                        {renderStars(review.rating)}
                      </span>
                    </div>
                    <div className="max-w-md">
                      <div className="line-clamp-2 break-words text-sm text-chrome-300" title={review.text}>
                        {review.text}
                      </div>
                    </div>
                    <div>
                      {getSentimentBadge(review.sentiment)}
                    </div>
                    <div className="text-sm text-chrome-300">{review.threat_level ?? '—'}</div>
                    <div className="text-sm text-chrome-300">{review.tags.join(', ') || '—'}</div>
                    <div className="font-mono text-xs text-chrome-400 whitespace-nowrap">
                      {formatDate(review.created_at)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Modal */}
      <ReviewDetailModal
        review={selectedReview}
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
      />
    </>
  );
}

export function ReviewsTable(props: ReviewsTableProps) {
  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <ReviewsTableContent {...props} />
    </ErrorBoundary>
  );
}
