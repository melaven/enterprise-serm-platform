import { useId, useRef, useState, type FormEvent } from 'react';

import { AnalysisPanel } from '@/components/AnalysisPanel';
import { ReviewsTable } from '@/components/ReviewsTable';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { parserApi, reviewsApi } from '@/lib/api/index.ts';
import type { Platform } from '@/lib/api/parser.ts';
import { useAnalytics } from '@/lib/useAnalytics.ts';
import { useParsingJob } from '@/lib/useParsingJob.ts';

const PLATFORMS: ReadonlyArray<{ value: Platform; label: string }> = [
  { value: 'trustpilot', label: 'Trustpilot' },
  { value: 'yandex', label: 'Яндекс.Карты' },
  { value: '2gis', label: '2ГИС' },
  { value: 'google', label: 'Google' },
];

const LABEL = 'block text-xs font-medium uppercase tracking-wider text-zinc-400';
const SELECT =
  'h-11 w-full rounded-sm border border-zinc-800 bg-zinc-950 px-4 text-sm text-white focus-visible:border-lime focus-visible:outline-none disabled:opacity-40';

const PAGE_SIZE = 20;

export function ReviewsPage() {
  const uid = useId();
  const urlRef = useRef<HTMLInputElement>(null);
  const [platform, setPlatform] = useState<Platform>('trustpilot');
  const [url, setUrl] = useState('');
  const analytics = useAnalytics(reviewsApi, { pageSize: PAGE_SIZE });
  const { isParsing, phase, start } = useParsingJob(parserApi, () => analytics.refetch());
  const focusUrl = () => urlRef.current?.focus();

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void start(platform, url.trim());
  }

  return (
    <div className="space-y-8">
      {analytics.summaryError && !analytics.summary ? (
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-6 border border-zinc-800 border-l-2 border-l-danger p-6"
        >
          <p className="text-sm text-zinc-400">Не удалось загрузить аналитику: {analytics.summaryError}</p>
          <Button variant="outline" onClick={analytics.refetch}>
            Повторить
          </Button>
        </div>
      ) : (
        <AnalysisPanel
          data={analytics.summary}
          isLoading={analytics.summaryLoading}
          online={analytics.online}
          isParsing={isParsing}
          onStartParsing={focusUrl}
        />
      )}

      <form
        onSubmit={handleSubmit}
        className="grid gap-6 border border-zinc-800 bg-zinc-950 p-8 md:grid-cols-[14rem_1fr_auto] md:items-end"
      >
        <div className="space-y-2">
          <label htmlFor={`${uid}-platform`} className={LABEL}>
            Площадка
          </label>
          <select
            id={`${uid}-platform`}
            className={SELECT}
            value={platform}
            onChange={(e) => setPlatform(e.target.value as Platform)}
            disabled={isParsing}
          >
            {PLATFORMS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label htmlFor={`${uid}-url`} className={LABEL}>
            Ссылка на страницу компании
          </label>
          <Input
            ref={urlRef}
            id={`${uid}-url`}
            type="url"
            required
            placeholder="https://"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={isParsing}
          />
        </div>
        <Button type="submit" disabled={isParsing}>
          {phase === 'starting' ? 'Запуск…' : phase === 'running' ? 'Сбор идёт…' : 'Запустить сбор'}
        </Button>
      </form>

      <ReviewsTable
        reviews={analytics.reviews}
        total={analytics.total}
        isLoading={analytics.reviewsLoading}
        error={analytics.reviewsError}
        pagination={{ page: analytics.page, pageSize: analytics.pageSize, onPageChange: analytics.setPage }}
        onStartParsing={focusUrl}
      />
    </div>
  );
}
