import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronsUpDown,
  Database,
  Hourglass,
  ShieldAlert,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// ── Типы данных (поля как в API, snake_case) ─────────────────────────────────

export type Sentiment = 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
export type Platform = '2gis' | 'yandex' | 'google' | 'trustpilot';

/** Отзыв с AI-разметкой. `ai_pending=true`: разметки ещё нет, её доделает фоновый ретрай. */
export interface EnrichedReview {
  id: string;
  platform: Platform;
  author_name: string | null;
  rating: number | null; // 1..5
  text: string;
  published_at: string | null; // ISO
  sentiment: Sentiment | null;
  ai_tags: string[];
  is_critical: boolean;
  ai_reply_draft: string | null; // черновик ответа от AI
  reply_text: string | null; // фактически опубликованный ответ
  ai_pending: boolean;
}

/** Алиас для обратной совместимости со старым названием. */
export type ReviewItem = EnrichedReview;

export type ReplyStatus = 'replied' | 'draft' | 'ai_pending' | 'none';

export function getReplyStatus(r: Pick<EnrichedReview, 'reply_text' | 'ai_reply_draft' | 'ai_pending'>): ReplyStatus {
  if (r.reply_text) return 'replied';
  if (r.ai_reply_draft) return 'draft';
  if (r.ai_pending) return 'ai_pending';
  return 'none';
}

export interface ReviewsPagination {
  /** С нуля. */
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export interface ReviewsTableProps {
  reviews: readonly EnrichedReview[];
  /** Всего отзывов на сервере (не только на странице). */
  total: number;
  isLoading?: boolean;
  /** Показывается вместо таблицы при ошибке загрузки. */
  error?: string | null;
  pagination?: ReviewsPagination;
  /** Кнопка в пустом состоянии. */
  onStartParsing?: () => void;
  className?: string;
}

// ── Справочники ──────────────────────────────────────────────────────────────

const PLATFORM_LABEL: Record<Platform, string> = {
  '2gis': '2ГИС',
  yandex: 'Яндекс',
  google: 'Google',
  trustpilot: 'Trustpilot',
};

const SENTIMENT_LABEL: Record<Sentiment, string> = {
  POSITIVE: 'Позитив',
  NEUTRAL: 'Нейтрально',
  NEGATIVE: 'Негатив',
};

const SENTIMENT_STYLE: Record<Sentiment, string> = {
  POSITIVE: 'border-lime bg-lime text-black',
  NEUTRAL: 'border-zinc-700 text-zinc-300',
  NEGATIVE: 'border-plum bg-plum text-white',
};

// Для сортировки: «хуже» первым при возрастании.
const SENTIMENT_RANK: Record<Sentiment, number> = { NEGATIVE: 0, NEUTRAL: 1, POSITIVE: 2 };
const STATUS_RANK: Record<ReplyStatus, number> = { ai_pending: 0, none: 1, draft: 2, replied: 3 };

const BADGE =
  'inline-flex items-center gap-1.5 rounded-sm border px-2 py-1 text-xs font-semibold uppercase leading-none tracking-wider';
const TEXT_CLAMP_CHARS = 140;
const MAX_VISIBLE_TAGS = 3;

type SortKey = 'platform' | 'sentiment' | 'status';
interface SortState {
  key: SortKey;
  dir: 'asc' | 'desc';
}

function sortValue(r: EnrichedReview, key: SortKey): number | string {
  switch (key) {
    case 'platform':
      return PLATFORM_LABEL[r.platform];
    case 'sentiment':
      return r.sentiment ? SENTIMENT_RANK[r.sentiment] : 3; // без разметки — в конец
    case 'status':
      return STATUS_RANK[getReplyStatus(r)];
  }
}

function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// ── Ячейки ───────────────────────────────────────────────────────────────────

function SentimentBadge({ sentiment, pending }: { sentiment: Sentiment | null; pending: boolean }) {
  if (sentiment) {
    return <span className={cn(BADGE, SENTIMENT_STYLE[sentiment])}>{SENTIMENT_LABEL[sentiment]}</span>;
  }
  return (
    <span className={cn(BADGE, 'border-zinc-800 text-zinc-500')}>{pending ? 'Ожидает AI' : '—'}</span>
  );
}

function TagList({ tags }: { tags: string[] }) {
  if (tags.length === 0) return <span className="text-zinc-600">—</span>;
  const visible = tags.slice(0, MAX_VISIBLE_TAGS);
  const rest = tags.length - visible.length;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="AI-теги" title={tags.join(', ')}>
      {visible.map((tag) => (
        <li key={tag} className="rounded-sm border border-zinc-700 px-2 py-1 text-xs text-zinc-300">
          {tag}
        </li>
      ))}
      {rest > 0 ? (
        <li className="rounded-sm border border-zinc-800 px-2 py-1 text-xs text-zinc-500">+{rest}</li>
      ) : null}
    </ul>
  );
}

function ReplyStatusCell({ status }: { status: ReplyStatus }) {
  switch (status) {
    case 'replied':
      return (
        <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-lime">
          <Check className="size-4" strokeWidth={2} aria-hidden="true" />
          Отвечено
        </span>
      );
    case 'draft':
      return <span className={cn(BADGE, 'border-plum bg-plum text-white')}>Черновик AI</span>;
    case 'ai_pending':
      return (
        <span className="inline-flex items-center gap-2 text-xs uppercase tracking-wider text-zinc-500">
          <Hourglass className="size-4" strokeWidth={1.5} aria-hidden="true" />В очереди AI
        </span>
      );
    case 'none':
      return <span className="text-xs uppercase tracking-wider text-zinc-500">Без ответа</span>;
  }
}

function SortHeader({
  label,
  sortKey,
  sort,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  sort: SortState | null;
  onSort: (key: SortKey) => void;
}) {
  const current = sort?.key === sortKey ? sort : null;
  const active = current !== null;
  const Icon = current === null ? ChevronsUpDown : current.dir === 'asc' ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      aria-sort={current === null ? 'none' : current.dir === 'asc' ? 'ascending' : 'descending'}
      className="px-6 py-4 text-left"
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className={cn(
          'inline-flex items-center gap-2 text-xs font-medium uppercase tracking-wider hover:text-white',
          active ? 'text-white' : 'text-zinc-400',
        )}
      >
        {label}
        <Icon className="size-3.5" strokeWidth={1.75} aria-hidden="true" />
      </button>
    </th>
  );
}

function PlainHeader({ children }: { children: React.ReactNode }) {
  return (
    <th scope="col" className="px-6 py-4 text-left text-xs font-medium uppercase tracking-wider text-zinc-400">
      {children}
    </th>
  );
}

function ReviewRow({
  review,
  expanded,
  onToggle,
}: {
  review: EnrichedReview;
  expanded: boolean;
  onToggle: () => void;
}) {
  const long = review.text.length > TEXT_CLAMP_CHARS;
  const date = formatDate(review.published_at);
  const meta = [review.author_name ?? 'Аноним', review.rating ? `${review.rating}/5` : null, date]
    .filter(Boolean)
    .join(' · ');

  return (
    <tr className={cn('align-top hover:bg-zinc-900/50', review.is_critical && 'bg-danger/5')}>
      {/* Левая рамка критичности: на первой ячейке, чтобы работала при border-collapse */}
      <td
        className={cn(
          'border-l-2 px-6 py-5 text-xs uppercase tracking-wider text-zinc-400',
          review.is_critical ? 'border-l-danger' : 'border-l-transparent',
        )}
      >
        {PLATFORM_LABEL[review.platform]}
      </td>

      <td className="max-w-lg px-6 py-5">
        <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-zinc-500">
          <span>{meta}</span>
          {review.is_critical ? (
            <span className={cn(BADGE, 'border-danger text-danger')}>
              <ShieldAlert className="size-3.5" strokeWidth={2} aria-hidden="true" />
              Критично
            </span>
          ) : null}
        </div>
        <p className={cn('text-sm leading-relaxed text-zinc-300', !expanded && 'line-clamp-2')}>
          {review.text || <span className="text-zinc-600">Без текста</span>}
        </p>
        {long ? (
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            className="mt-2 text-xs uppercase tracking-wider text-zinc-500 hover:text-white"
          >
            {expanded ? 'Свернуть' : 'Показать полностью'}
          </button>
        ) : null}
      </td>

      <td className="px-6 py-5">
        <SentimentBadge sentiment={review.sentiment} pending={review.ai_pending} />
      </td>
      <td className="px-6 py-5">
        <TagList tags={review.ai_tags} />
      </td>
      <td className="px-6 py-5">
        <ReplyStatusCell status={getReplyStatus(review)} />
      </td>
    </tr>
  );
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 5 }, (_, i) => (
        <tr key={i} aria-hidden="true">
          <td className="border-l-2 border-l-transparent px-6 py-5">
            <Skeleton className="h-4 w-16" />
          </td>
          <td className="px-6 py-5">
            <Skeleton className="h-3 w-40" />
            <Skeleton className="mt-3 h-4 w-full max-w-md" />
          </td>
          <td className="px-6 py-5">
            <Skeleton className="h-6 w-24" />
          </td>
          <td className="px-6 py-5">
            <Skeleton className="h-6 w-32" />
          </td>
          <td className="px-6 py-5">
            <Skeleton className="h-4 w-24" />
          </td>
        </tr>
      ))}
    </>
  );
}

// ── Компонент ────────────────────────────────────────────────────────────────

export function ReviewsTable({
  reviews,
  total,
  isLoading = false,
  error = null,
  pagination,
  onStartParsing,
  className,
}: ReviewsTableProps) {
  const [sort, setSort] = useState<SortState | null>(null);
  const [onlyCritical, setOnlyCritical] = useState(false);
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());

  const criticalCount = useMemo(() => reviews.filter((r) => r.is_critical).length, [reviews]);

  const rows = useMemo(() => {
    const filtered = onlyCritical ? reviews.filter((r) => r.is_critical) : [...reviews];
    if (!sort) return filtered;
    const sign = sort.dir === 'asc' ? 1 : -1;
    return filtered.sort((a, b) => {
      const av = sortValue(a, sort.key);
      const bv = sortValue(b, sort.key);
      const cmp =
        typeof av === 'number' && typeof bv === 'number'
          ? av - bv
          : String(av).localeCompare(String(bv), 'ru');
      return cmp * sign; // sort стабилен: равные сохраняют порядок API
    });
  }, [reviews, sort, onlyCritical]);

  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s?.key !== key ? { key, dir: 'asc' } : s.dir === 'asc' ? { key, dir: 'desc' } : null,
    );

  const toggleExpanded = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  const empty = !isLoading && !error && reviews.length === 0;
  const pages = pagination ? Math.max(1, Math.ceil(total / pagination.pageSize)) : 1;

  return (
    <section aria-labelledby="reviews-title" className={cn('border border-zinc-800 bg-zinc-950', className)}>
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 px-8 py-6">
        <div className="flex items-baseline gap-6">
          <h2 id="reviews-title" className="text-xs font-medium uppercase tracking-wider text-zinc-400">
            Отзывы
          </h2>
          <span className="text-xs uppercase tracking-wider text-zinc-400 tabular-nums">
            Всего: <span className="text-white">{total.toLocaleString('ru-RU')}</span>
          </span>
        </div>
        <button
          type="button"
          aria-pressed={onlyCritical}
          onClick={() => setOnlyCritical((v) => !v)}
          disabled={criticalCount === 0 && !onlyCritical}
          className={cn(
            'inline-flex h-9 items-center gap-2 rounded-sm border px-4 text-xs font-semibold uppercase tracking-wider disabled:cursor-not-allowed disabled:opacity-40',
            onlyCritical
              ? 'border-danger bg-danger/10 text-danger'
              : 'border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-white',
          )}
        >
          <ShieldAlert className="size-4" strokeWidth={1.75} aria-hidden="true" />
          Критичные <span className="tabular-nums">{criticalCount}</span>
        </button>
      </header>

      {error ? (
        <div role="alert" className="px-8 py-16 text-center text-sm text-danger">
          {error}
        </div>
      ) : empty ? (
        <div className="flex flex-col items-center px-8 py-20 text-center">
          <Database className="mx-auto mb-4 h-12 w-12 text-zinc-700" strokeWidth={1.25} aria-hidden="true" />
          <p className="text-sm font-medium uppercase tracking-wider text-zinc-300">Отзывов пока нет</p>
          <p className="mt-2 max-w-sm text-sm text-zinc-500">
            Запустите сбор, чтобы загрузить отзывы с подключённых площадок.
          </p>
          {onStartParsing ? (
            <Button className="mt-8" onClick={onStartParsing}>
              Запустить сбор
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse text-left" aria-busy={isLoading}>
            <thead>
              <tr className="border-b border-zinc-800">
                <SortHeader label="Платформа" sortKey="platform" sort={sort} onSort={toggleSort} />
                <PlainHeader>Текст</PlainHeader>
                <SortHeader label="Тональность" sortKey="sentiment" sort={sort} onSort={toggleSort} />
                <PlainHeader>AI-теги</PlainHeader>
                <SortHeader label="Статус ответа" sortKey="status" sort={sort} onSort={toggleSort} />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900">
              {isLoading ? (
                <SkeletonRows />
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-sm text-zinc-500">
                    Нет отзывов, подходящих под фильтр
                  </td>
                </tr>
              ) : (
                rows.map((review) => (
                  <ReviewRow
                    key={review.id}
                    review={review}
                    expanded={expanded.has(review.id)}
                    onToggle={() => toggleExpanded(review.id)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {pagination && !error && !empty ? (
        <footer className="flex items-center justify-between border-t border-zinc-800 px-8 py-4">
          <span className="text-xs uppercase tracking-wider text-zinc-400 tabular-nums">
            Стр. <span className="text-white">{pagination.page + 1}</span> из {pages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page === 0 || isLoading}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
            >
              Назад
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page + 1 >= pages || isLoading}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
            >
              Далее
            </Button>
          </div>
        </footer>
      ) : null}
    </section>
  );
}
