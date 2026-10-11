import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import apiClient from '../api/client';
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
 * Таблица отзывов с реальным API
 * Flat-design, без теней
 */

interface Review {
  id: string;
  platform: string;
  author: string;
  rating: number;
  text: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
  created_at: string;
  status?: 'new' | 'processing' | 'analyzed';
  external_review_id?: string;
}

export const ReviewsTable = () => {
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReviews();
  }, []);

  const fetchReviews = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/v1/reviews');
      setReviews(response.data.items || response.data);
    } catch (err: any) {
      console.error('Failed to fetch reviews:', err);
      
      if (err.response?.status === 402) {
        toast.error('Ошибка биллинга: Лимит токенов или запросов исчерпан', {
          duration: 5000,
        });
      } else {
        toast.error('Не удалось загрузить отзывы');
      }
      
      setReviews([]);
    } finally {
      setLoading(false);
    }
  };

  const getSentimentBadge = (sentiment?: Review['sentiment']) => {
    if (!sentiment) return <Badge variant="secondary">Не определена</Badge>;
    
    switch (sentiment) {
      case 'positive':
        return <Badge variant="success">Позитивный</Badge>;
      case 'negative':
        return <Badge variant="destructive">Негативный</Badge>;
      case 'neutral':
        return <Badge variant="secondary">Нейтральный</Badge>;
    }
  };

  const getStatusBadge = (status?: Review['status']) => {
    if (!status) return <Badge variant="outline">Новый</Badge>;
    
    switch (status) {
      case 'analyzed':
        return <Badge variant="success">Проанализирован</Badge>;
      case 'processing':
        return <Badge variant="default">Обработка</Badge>;
      case 'new':
        return <Badge variant="outline">Новый</Badge>;
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
  if (loading) {
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
          <Button variant="outline" onClick={fetchReviews}>
            Обновить
          </Button>
        </div>

        {/* Empty State */}
        <div className="flex flex-col items-center justify-center py-12">
          <div className="w-16 h-16 bg-chrome-600/20 rounded-none flex items-center justify-center mb-4">
            <span className="text-3xl text-chrome-500">📋</span>
          </div>
          <h4 className="text-lg font-medium text-chrome-300 mb-2">
            Нет отзывов
          </h4>
          <p className="text-sm text-chrome-500 text-center max-w-md">
            Отзывы появятся здесь после запуска сбора данных.
            Нажмите кнопку "Запустить сбор" чтобы начать.
          </p>
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
            Всего {reviews.length} отзывов
          </p>
        </div>
        <Button variant="outline" onClick={fetchReviews}>
          Обновить
        </Button>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Платформа</TableHead>
            <TableHead>Автор</TableHead>
            <TableHead>Рейтинг</TableHead>
            <TableHead>Отзыв</TableHead>
            <TableHead>Тональность</TableHead>
            <TableHead>Статус</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead className="text-right">Действия</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {reviews.map((review) => (
            <TableRow key={review.id}>
              <TableCell className="font-medium">
                {review.platform}
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
              <TableCell>
                {getStatusBadge(review.status)}
              </TableCell>
              <TableCell className="font-mono text-xs text-chrome-400">
                {formatDate(review.created_at)}
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
