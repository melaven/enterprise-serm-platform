import { CheckCircle2, Edit3, Calendar, Star, User, MessageSquare } from 'lucide-react';
import { Review } from '@/api/services';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
  DialogBody,
  DialogFooter,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export interface ReviewDetailModalProps {
  review: Review | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove?: (reviewId: string) => void;
  isApproving?: boolean;
  onEdit?: (reviewId: string) => void;
}

/**
 * Детальный просмотр отзыва и AI-ответа.
 */
export function ReviewDetailModal({
  review,
  open,
  onOpenChange,
  onApprove,
  isApproving = false,
  onEdit,
}: ReviewDetailModalProps) {
  if (!review) return null;

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

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

  const renderStars = (rating: number) => {
    return '★'.repeat(Math.min(rating, 5)) + '☆'.repeat(Math.max(5 - rating, 0));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Детали отзыва</DialogTitle>
          <DialogClose onClose={() => onOpenChange(false)} />
        </DialogHeader>

        <DialogBody>
          {/* Метаданные */}
          <div className="grid grid-cols-2 gap-4 rounded-sm border-2 border-chrome-600 bg-ink-900 p-4">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-plum" />
              <div>
                <p className="text-xs text-chrome-400">Автор</p>
                <p className="text-sm font-medium text-white">{review.author_name || 'Аноним'}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-plum" />
              <div>
                <p className="text-xs text-chrome-400">Дата</p>
                <p className="font-mono text-xs text-chrome-300">{formatDate(review.created_at)}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Star className="h-4 w-4 text-plum" />
              <div>
                <p className="text-xs text-chrome-400">Рейтинг</p>
                <p className="font-mono text-sm text-lime">{renderStars(review.rating)}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-plum" />
              <div>
                <p className="text-xs text-chrome-400">Тональность</p>
                <div className="mt-1">{getSentimentBadge(review.sentiment)}</div>
              </div>
            </div>
          </div>

          {/* Текст отзыва */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-white">Текст отзыва</h4>
            <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-4">
              <p className="text-sm leading-relaxed text-chrome-200 break-words whitespace-pre-wrap">
                {review.text}
              </p>
            </div>
          </div>

          {/* AI-генерированный ответ */}
          <div className="space-y-2">
            <h4 className="flex items-center gap-2 text-sm font-semibold text-white">
              <span 
                className="flex h-6 w-6 items-center justify-center rounded-sm bg-plum text-xs font-bold text-white"
                aria-label="AI"
              >
                AI
              </span>
              Предложенный ответ
            </h4>
            <div className="rounded-sm border-2 border-plum bg-ink-900 p-4">
              <p className="text-sm leading-relaxed text-chrome-200 break-words whitespace-pre-wrap">
                {review.auto_reply || 'AI-ответ для этого отзыва не подготовлен.'}
              </p>
            </div>
          </div>

          {/* Статус */}
          {review.is_critical && (
            <div className="rounded-sm border-2 border-destructive bg-destructive/10 p-3">
              <p className="text-sm font-medium text-destructive">
                ⚠️ Критический отзыв — требует срочного внимания
              </p>
            </div>
          )}
        </DialogBody>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Закрыть
          </Button>
          {onEdit && (
            <Button variant="default" onClick={() => onEdit(review.id)}>
              <Edit3 className="mr-2 h-4 w-4" />
              Редактировать
            </Button>
          )}
          {onApprove && review.ai_pending && review.auto_reply && (
            <Button
              variant="accent"
              disabled={isApproving}
              onClick={() => onApprove(review.id)}
            >
              <CheckCircle2 className="mr-2 h-4 w-4" />
              {isApproving ? 'Подтверждаем…' : 'Одобрить AI-ответ'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
