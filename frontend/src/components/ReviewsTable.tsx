import { useEffect } from 'react';
import { Database } from 'lucide-react';
import { useReviews } from '../store/useAppStore';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from './ui/table';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Skeleton } from './ui/skeleton';

/**
 * Таблица отзывов
 * Использует centralized API через Zustand store
 */
export const ReviewsTable = () => {
  const { reviews, reviewsLoading, reviewsTotal, fetchReviews } = useReviews();

  useEffect(() => {
    fetchReviews({ limit: 50 });
  }, [fetchReviews]);

  const getSentimentBadge = (sentiment: string | null) => {
    if (!sentiment) return <Badge variant="secondary">Не определена</Badge>;
    
    switch (sentiment.toLowerCase()) {
      case 'positive':
        return <Badge variant="success">Позитивный</Badge>;
      case 'negative':
        return <Badge variant="destructive">Негативный</Badge>;
      case 'neutral':
        return <Badge variant="secondary">Нейтральный</Badge>;
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
      <div className="card p-6">
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
  if (reviews.length === 0) {
    return (
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-xl font-semibold text-chrome-300">
              Отзывы
            </h3>
            <p className="text-sm text-chrome-500 mt-1">
              Отзывы не найдены
            </p>
          </div>
          <Button variant="outline" onClick={() => fetchReviews({ limit: 50 })}>
            Обновить
          </Button>
        </div>

        {/* Empty State */}
        <div className="border border-zinc-800 rounded-sm bg-black p-12 text-center flex flex-col items-center justify-center">
          <Database className="w-12 h-12 text-zinc-700 mb-4" strokeWidth={1.25} />
          <h3 className="text-zinc-100 font-medium mb-1">Нет отзывов</h3>
          <p className="text-zinc-500 text-sm max-w-sm">Отзывы появятся здесь после запуска сбора данных.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-semibold text-chrome-300">
            Отзывы
          </h3>
          <p className="text-sm text-chrome-500 mt-1">
            Всего {reviewsTotal} отзывов
          </p>
        </div>
        <Button variant="outline" onClick={() => fetchReviews({ limit: 50 })}>
          Обновить
        </Button>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Источник</TableHead>
            <TableHead>Автор</TableHead>
            <TableHead>Рейтинг</TableHead>
            <TableHead>Отзыв</TableHead>
            <TableHead>Тональность</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead className="text-right">Действия</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {reviews.map((review) => (
            <TableRow key={review.id}>
              <TableCell className="font-medium">
                {review.source}
              </TableCell>
              <TableCell>{review.author || 'Аноним'}</TableCell>
              <TableCell>
                <span className="text-[#C5FF4A] font-mono text-sm">
                  {renderStars(review.rating)}
                </span>
              </TableCell>
              <TableCell className="max-w-md">
                <div className="truncate">{review.text}</div>
              </TableCell>
              <TableCell>
                {getSentimentBadge(review.sentiment)}
              </TableCell>
              <TableCell className="font-mono text-xs text-chrome-400">
                {formatDate(review.date)}
              </TableCell>
              <TableCell className="text-right">
                <Button variant="ghost" size="sm">
                  Детали
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};
