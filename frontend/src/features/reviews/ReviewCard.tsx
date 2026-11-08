import { useState } from 'react';
import type { Review } from '@/api/services';
import { useApproveReply } from '@/hooks/useApproveReply';

interface ReviewCardProps {
  review: Review;
  onArchive: () => void;
  isPending?: boolean;
}

/**
 * ReviewCard — Premium B2B review display component
 *
 * Design System: Clean slate palette with excellent contrast and readability
 * Features: SI-generated reply block with inline editing and Approve action
 */
export function ReviewCard({ review, onArchive, isPending = false }: ReviewCardProps) {
  const [isEditingReply, setIsEditingReply] = useState(false);
  const [editedReply, setEditedReply] = useState(review.generated_reply || '');
  
  const approveReply = useApproveReply();
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
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'NEGATIVE':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'NEUTRAL':
        return 'bg-slate-50 text-slate-600 border-slate-200';
      default:
        return 'bg-slate-50 text-slate-500 border-slate-200';
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-sm p-5 hover:border-slate-300 transition-colors">
      {/* Header: Platform, Date, Sentiment */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            {review.platform || 'Unknown'}
          </span>
          <span className="text-xs text-slate-400">
            {formatDate(review.created_at)}
          </span>
        </div>
        <span
          className={`
            inline-flex items-center
            px-2.5 py-1
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
              className={`text-base ${
                star <= review.rating ? 'text-amber-400' : 'text-slate-300'
              }`}
            >
              ★
            </span>
          ))}
        </div>
        <span className="text-sm text-slate-500 ml-1">
          {review.rating}/5
        </span>
      </div>

      {/* Review Text — Excellent readability */}
      <p className="text-sm text-slate-800 mb-4 leading-relaxed">
        {review.text}
      </p>

      {/* SI-Generated Reply Block */}
      {review.generated_reply && (
        <div className="mt-4 p-4 bg-slate-50 border-l-2 border-slate-400 rounded-r-md">
          <div className="flex items-center gap-1.5 mb-2">
            <svg
              className="w-3.5 h-3.5 text-slate-500"
              fill="currentColor"
              viewBox="0 0 20 20"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            <span className="text-xs text-slate-500 uppercase font-semibold tracking-wide">
              SentiGuard SI Draft
            </span>
          </div>

          {/* Display or Edit Mode */}
          {isEditingReply ? (
            <>
              {/* Textarea for editing */}
              <textarea
                value={editedReply}
                onChange={(e) => setEditedReply(e.target.value)}
                className="
                  w-full 
                  min-h-[120px] 
                  p-3 
                  text-sm 
                  text-slate-800 
                  bg-white 
                  border 
                  border-slate-300 
                  rounded-md 
                  focus:ring-2 
                  focus:ring-slate-500 
                  focus:border-slate-500 
                  focus:outline-none
                  resize-y
                  placeholder:text-slate-400
                "
                placeholder="Введите текст ответа..."
              />

              {/* Edit Action Panel */}
              <div className="flex items-center justify-end gap-2 mt-3">
                <button
                  onClick={() => {
                    setIsEditingReply(false);
                    setEditedReply(review.generated_reply || '');
                  }}
                  disabled={approveReply.isPending}
                  className="
                    text-sm 
                    font-medium 
                    px-3 
                    py-1.5 
                    text-slate-500 
                    hover:text-slate-700
                    hover:bg-slate-100
                    rounded-md 
                    transition-colors
                    disabled:opacity-50
                    disabled:cursor-not-allowed
                  "
                >
                  Отмена
                </button>
                <button
                  onClick={() => {
                    approveReply.mutate(
                      {
                        reviewId: review.id,
                        content: editedReply,
                      },
                      {
                        onSuccess: () => {
                          setIsEditingReply(false);
                        },
                      }
                    );
                  }}
                  disabled={approveReply.isPending || !editedReply.trim()}
                  className="
                    text-sm 
                    font-medium 
                    px-4 
                    py-1.5 
                    bg-slate-900 
                    text-white 
                    rounded-md 
                    hover:bg-slate-800 
                    active:bg-slate-950
                    transition-colors
                    focus:outline-none 
                    focus:ring-2 
                    focus:ring-slate-500 
                    focus:ring-offset-2
                    disabled:opacity-50
                    disabled:cursor-not-allowed
                  "
                >
                  {approveReply.isPending ? 'Утверждаем...' : 'Сохранить и утвердить'}
                </button>
              </div>
            </>
          ) : (
            <>
              {/* Display Mode */}
              <p className="text-sm text-slate-700 whitespace-pre-wrap mb-3">
                {review.generated_reply}
              </p>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsEditingReply(true)}
                  className="
                    flex-1
                    inline-flex
                    items-center
                    justify-center
                    gap-1.5
                    text-sm 
                    font-medium 
                    px-4 
                    py-2 
                    text-slate-600 
                    bg-white 
                    border 
                    border-slate-200 
                    rounded-sm 
                    hover:text-slate-900 
                    hover:bg-slate-50
                    hover:border-slate-300
                    active:bg-slate-100
                    transition-colors
                    focus:outline-none 
                    focus:ring-2 
                    focus:ring-slate-500 
                    focus:ring-offset-2
                  "
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                    />
                  </svg>
                  Изменить
                </button>

                <button
                  onClick={() =>
                    approveReply.mutate({
                      reviewId: review.id,
                      content: review.generated_reply || '',
                    })
                  }
                  disabled={approveReply.isPending}
                  className="
                    flex-1
                    bg-slate-900 
                    text-white 
                    text-sm 
                    font-medium 
                    px-4 
                    py-2 
                    rounded-sm 
                    hover:bg-slate-800 
                    active:bg-slate-950
                    transition-colors 
                    duration-150
                    focus:outline-none 
                    focus:ring-2 
                    focus:ring-slate-500 
                    focus:ring-offset-2
                    disabled:opacity-50
                    disabled:cursor-not-allowed
                  "
                >
                  {approveReply.isPending ? 'Утверждаем...' : 'Утвердить ответ'}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Footer: Author & Archive Button */}
      <div className="flex items-center justify-between pt-3 mt-3 border-t border-slate-200">
        {review.author_name && (
          <span className="text-xs text-slate-500 font-medium">
            {review.author_name}
          </span>
        )}
        <button
          onClick={onArchive}
          disabled={isPending}
          className={`
            text-sm
            font-medium
            px-3 
            py-1.5
            border
            rounded-sm
            transition-colors 
            duration-150
            ${
              isPending
                ? 'bg-slate-50 text-slate-400 border-slate-200 cursor-not-allowed'
                : 'bg-white text-slate-600 border-slate-300 hover:text-slate-900 hover:bg-slate-50 hover:border-slate-400'
            }
          `}
        >
          {isPending ? 'Архивация...' : 'В архив'}
        </button>
      </div>
    </div>
  );
}
