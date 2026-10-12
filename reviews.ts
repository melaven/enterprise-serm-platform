import type { AxiosInstance } from 'axios';

import type { AnalysisData, SentimentDistribution } from '@/components/AnalysisPanel';
import type { EnrichedReview, Platform, Sentiment } from '@/components/ReviewsTable';

// ── Формат ответов бэкенда (wire) ────────────────────────────────────────────
// Мапперы терпимы к полям, которых бэкенд может ещё не отдавать: недостающее
// превращается в null/пустое значение, а не в выдуманное число.

export interface ReviewWire {
  id: string;
  platform: Platform;
  author_name?: string | null;
  rating?: number | null; // 0..5, 0 = без оценки
  /** Текст отзыва. Старые ответы называют поле `body`. */
  text?: string | null;
  body?: string | null;
  published_at?: string | null;
  sentiment?: Sentiment | null;
  ai_tags?: string[] | null;
  is_critical?: boolean | null;
  ai_reply_draft?: string | null;
  reply_text?: string | null;
  ai_pending?: boolean | null;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export interface SummaryWire {
  total_reviews: number;
  average_rating: number | null;
  sentiment: SentimentDistribution;
  /** Точка графика: `reviews` (как в /analytics) или `count`. */
  timeline: Array<{ date: string; reviews?: number; count?: number }>;
  critical_reviews?: number | null;
  ai_pending?: number | null;
  period?: { date_from: string; date_to: string } | string | null;
}

export interface ReviewsPageData {
  items: EnrichedReview[];
  total: number;
}

// ── Мапперы ──────────────────────────────────────────────────────────────────

export function mapReview(r: ReviewWire): EnrichedReview {
  return {
    id: r.id,
    platform: r.platform,
    author_name: r.author_name ?? null,
    rating: typeof r.rating === 'number' && r.rating >= 1 ? r.rating : null,
    text: r.text ?? r.body ?? '',
    published_at: r.published_at ?? null,
    sentiment: r.sentiment ?? null,
    ai_tags: r.ai_tags ?? [],
    is_critical: r.is_critical === true,
    ai_reply_draft: r.ai_reply_draft ?? null,
    reply_text: r.reply_text ?? null,
    ai_pending: r.ai_pending === true,
  };
}

const shortDate = (iso: string): string => {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
};

function periodLabel(period: SummaryWire['period']): string | undefined {
  if (!period) return undefined;
  return typeof period === 'string' ? period : `${shortDate(period.date_from)} — ${shortDate(period.date_to)}`;
}

export function mapSummary(s: SummaryWire): AnalysisData {
  return {
    total_reviews: s.total_reviews,
    average_rating: s.average_rating,
    sentiment: s.sentiment,
    timeline: s.timeline.map((p) => ({ date: p.date, count: p.count ?? p.reviews ?? 0 })),
    critical_reviews: s.critical_reviews ?? null,
    ai_pending: s.ai_pending ?? null,
    period: periodLabel(s.period),
  };
}

// ── API ──────────────────────────────────────────────────────────────────────

export function createReviewsApi(client: AxiosInstance) {
  return {
    /** GET /api/v1/reviews?limit&offset. 402 открывает глобальную модалку (интерцептор). */
    async list(query: { limit: number; offset: number }, signal?: AbortSignal): Promise<ReviewsPageData> {
      const { data } = await client.get<Page<ReviewWire>>('/api/v1/reviews', { params: query, signal });
      return { items: data.items.map(mapReview), total: data.total };
    },

    /** GET /api/v1/reviews/summary. */
    async summary(signal?: AbortSignal): Promise<AnalysisData> {
      const { data } = await client.get<SummaryWire>('/api/v1/reviews/summary', { signal });
      return mapSummary(data);
    },
  };
}

export type ReviewsApi = ReturnType<typeof createReviewsApi>;
