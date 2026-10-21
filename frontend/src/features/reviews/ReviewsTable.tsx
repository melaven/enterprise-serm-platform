import { useEffect, useState } from 'react';
import { Database, Download } from 'lucide-react';
import { useReviews } from '../../store/useAppStore';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { Review } from '../../api/services';
import { ReviewDetailModal } from './ReviewDetailModal';

/**
 * Таблица отзывов
 * Использует centralized API через Zustand store
 */
export interface ReviewsTableProps {
  searchQuery?: string;
  sentimentFilter?: string;
  platformFilter?: string;
  onExportCSV?: () => void;
}

export const ReviewsTable = ({ searchQuery, sentimentFilter, platformFilter, onExportCSV }: ReviewsTableProps) => {
  const {
    reviews,
    reviewsLoading,
    reviewsTotal,
    fetchReviews,
  } = useReviews();
  const [selectedReview, setSelectedReview] = useState<Review | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    const params: {
      page_size: number;
      platform?: string;
      sentiment?: string;
      search?: string;
    } = { page_size: 50 };

    // Применяем фильтры только если они не "all"
    if (platformFilter && platformFilter !== 'all') {
      params.platform = platformFilter;
    }
    if (sentimentFilter && sentimentFilter !== 'all') {
      params.sentiment = sentimentFilter;
    }
    if (searchQuery?.trim()) {
      params.search = searchQuery.trim();
    }

    const timeoutId = window.setTimeout(() => {
      void fetchReviews(params);
    }, 250);
    return () => window.clearTimeout(timeoutId);
  }, [fetchReviews, platformFilter, searchQuery, sentimentFilter]);

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
  if (reviewsLoading) {
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
            onClick={() =>
              fetchReviews({
                page_size: 50,
                ...(platformFilter && platformFilter !== 'all' ? { platform: platformFilter } : {}),
                ...(sentimentFilter && sentimentFilter !== 'all' ? { sentiment: sentimentFilter } : {}),
                ...(searchQuery?.trim() ? { search: searchQuery.trim() } : {}),
              })
            }
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
              onClick={() =>
                fetchReviews({
                  page_size: 50,
                  ...(platformFilter && platformFilter !== 'all' ? { platform: platformFilter } : {}),
                  ...(sentimentFilter && sentimentFilter !== 'all' ? { sentiment: sentimentFilter } : {}),
                  ...(searchQuery?.trim() ? { search: searchQuery.trim() } : {}),
                })
              }
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
            <TableBody>
              {filteredReviews.map((review) => (
                <TableRow 
                  key={review.id}
                  className="cursor-pointer"
                  onClick={() => handleRowClick(review)}
                >
                  <TableCell className="font-medium">
                    {review.platform}
                  </TableCell>
                  <TableCell>
                    <span className="text-lime font-mono text-sm">
                      {renderStars(review.rating)}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-md">
                    <div className="line-clamp-2 break-words" title={review.text}>
                      {review.text}
                    </div>
                  </TableCell>
                  <TableCell>
                    {getSentimentBadge(review.sentiment)}
                  </TableCell>
                  <TableCell>{review.threat_level ?? '—'}</TableCell>
                  <TableCell>{review.tags.join(', ') || '—'}</TableCell>
                  <TableCell className="font-mono text-xs text-chrome-400 whitespace-nowrap">
                    {formatDate(review.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
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
};
