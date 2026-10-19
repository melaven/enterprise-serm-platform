import { useEffect, useState } from 'react';
import { CheckCircle2, Edit3, Calendar, Star, User, MessageSquare, Copy, Send, ShieldAlert } from 'lucide-react';
import { ApiError } from '@/api/client';
import { publishReviewReply, type Review } from '@/api/services';
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
import { toast } from 'sonner';

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
  const [replyDraft, setReplyDraft] = useState('');
  const [isPublishingReply, setIsPublishingReply] = useState(false);

  useEffect(() => {
    setReplyDraft(review?.suggested_reply || review?.auto_reply || '');
  }, [review?.id, review?.suggested_reply, review?.auto_reply]);

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

  const getThreatLevelIndicator = (level: number | null) => {
    if (!level) return null;

    const normalizedLevel = Math.min(Math.max(level, 1), 5);
    const colors = [
      'bg-chrome-600', // Level 1
      'bg-chrome-500', // Level 2
      'bg-chrome-400', // Level 3
      'bg-plum',       // Level 4
      'bg-destructive' // Level 5
    ];

    return (
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-plum" />
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className={`h-2 w-2 rounded-sm ${
                i <= normalizedLevel ? colors[normalizedLevel - 1] : 'bg-ink-950'
              }`}
            />
          ))}
        </div>
        <span className="text-xs text-chrome-300">{normalizedLevel}/5</span>
      </div>
    );
  };

  const handleCopyReply = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Ответ скопирован в буфер');
  };

  const handlePublishReply = async () => {
    if (!review || isPublishingReply) return;
    setIsPublishingReply(true);
    try {
      const result = await publishReviewReply(review.id, replyDraft);
      toast.success('Ответ поставлен в очередь на публикацию', {
        description: `Задача ${result.job_id}`,
      });
    } catch (error) {
      toast.error('Не удалось отправить ответ', {
        description: error instanceof ApiError ? error.message : 'Попробуйте позже.',
      });
    } finally {
      setIsPublishingReply(false);
    }
  };

  const canPublishReply =
    ['google', 'google_business'].includes((review.platform || '').toLowerCase()) &&
    Boolean(review.external_review_id);

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

            {review.threat_level && (
              <div className="col-span-2 flex items-center gap-2">
                <p className="text-xs text-chrome-400">Уровень угрозы</p>
                <div className="mt-1">{getThreatLevelIndicator(review.threat_level)}</div>
              </div>
            )}
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

          {/* SI-аналитика: suggested_reply */}
          {review.suggested_reply && (
            <div className="space-y-2">
              <h4 className="flex items-center gap-2 text-sm font-semibold text-white">
                <ShieldAlert className="h-4 w-4 text-plum" />
                Рекомендуемый ответ (SI)
              </h4>
              <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-4">
                <p className="mb-3 text-sm leading-relaxed text-chrome-200 break-words whitespace-pre-wrap">
                  {review.suggested_reply}
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopyReply(review.suggested_reply!)}
                  className="w-full"
                >
                  <Copy className="mr-2 h-4 w-4" />
                  Скопировать в буфер
                </Button>
              </div>
            </div>
          )}

          {canPublishReply && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-white">
                Ответить на площадке
              </h4>
              <textarea
                aria-label="Текст ответа для публикации"
                className="min-h-28 w-full rounded-sm border-2 border-chrome-600 bg-ink-900 p-3 text-sm text-chrome-200"
                maxLength={4096}
                value={replyDraft}
                onChange={(event) => setReplyDraft(event.target.value)}
              />
              <Button
                variant="accent"
                className="w-full"
                disabled={!replyDraft.trim() || isPublishingReply}
                onClick={handlePublishReply}
              >
                <Send className="mr-2 h-4 w-4" />
                {isPublishingReply ? 'Отправляем…' : 'Опубликовать ответ'}
              </Button>
            </div>
          )}

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
