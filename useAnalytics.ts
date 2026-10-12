import { useCallback, useEffect, useState } from 'react';

import type { AnalysisData } from '@/components/AnalysisPanel';
import type { EnrichedReview } from '@/components/ReviewsTable';

import { ApiError } from './api/client.ts';
import { isAbortError } from './api/parser.ts';
import type { ReviewsApi } from './api/reviews.ts';

interface Resource<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** Ошибка сети (а не ответ сервера): показываем «Офлайн». */
  offline: boolean;
}

const INITIAL: Resource<never> = { data: null, loading: true, error: null, offline: false };

function failure(prev: Resource<never> | Resource<unknown>, error: unknown) {
  return {
    data: prev.data,
    loading: false,
    error: error instanceof Error ? error.message : 'Не удалось загрузить данные',
    offline: error instanceof ApiError && error.code === 'NETWORK',
  };
}

export interface UseAnalyticsOptions {
  pageSize?: number;
}

export interface UseAnalyticsResult {
  summary: AnalysisData | null;
  summaryLoading: boolean;
  summaryError: string | null;
  /** false, если последний запрос не дошёл до сервера. */
  online: boolean;

  reviews: EnrichedReview[];
  total: number;
  reviewsLoading: boolean;
  reviewsError: string | null;

  /** С нуля. */
  page: number;
  pageSize: number;
  setPage: (page: number) => void;

  /** Перезапросить всё и вернуться на первую страницу (после сбора новых отзывов). */
  refetch: () => void;
}

/**
 * Данные дашборда: сводка и страница отзывов грузятся параллельно и независимо,
 * поэтому сбой одной части не роняет другую. Запросы идут через общий клиент с
 * интерцептором (JWT, 402 → модалка). Смена страницы/размонтирование отменяет
 * устаревшие запросы.
 */
export function useAnalytics(api: ReviewsApi, { pageSize = 20 }: UseAnalyticsOptions = {}): UseAnalyticsResult {
  const [page, setPage] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [summary, setSummary] = useState<Resource<AnalysisData>>(INITIAL);
  const [list, setList] = useState<Resource<{ items: EnrichedReview[]; total: number }>>(INITIAL);

  useEffect(() => {
    const controller = new AbortController();
    setSummary((s) => ({ ...s, loading: true, error: null }));
    api
      .summary(controller.signal)
      .then((data) => setSummary({ data, loading: false, error: null, offline: false }))
      .catch((error: unknown) => {
        if (!isAbortError(error)) setSummary((s) => failure(s, error));
      });
    return () => controller.abort();
  }, [api, reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    setList((s) => ({ ...s, loading: true, error: null }));
    api
      .list({ limit: pageSize, offset: page * pageSize }, controller.signal)
      .then((data) => setList({ data, loading: false, error: null, offline: false }))
      .catch((error: unknown) => {
        if (!isAbortError(error)) setList((s) => failure(s, error));
      });
    return () => controller.abort();
  }, [api, page, pageSize, reloadKey]);

  const refetch = useCallback(() => {
    setPage(0);
    setReloadKey((k) => k + 1);
  }, []);

  return {
    summary: summary.data,
    summaryLoading: summary.loading,
    summaryError: summary.error,
    online: !(summary.offline || list.offline),
    reviews: list.data?.items ?? [],
    total: list.data?.total ?? 0,
    reviewsLoading: list.loading,
    reviewsError: list.error,
    page,
    pageSize,
    setPage,
    refetch,
  };
}
