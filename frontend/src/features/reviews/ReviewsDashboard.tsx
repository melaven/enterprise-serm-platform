import { useEffect, useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { ArrowLeft, Inbox, Search, Sparkles, Star } from 'lucide-react';

import { fetchReviews } from '@/api/reviews';
import { useAuth } from '@/store/useAppStore';
import type { SanitizedReview } from '@/types/review';

// --------------------------------------------------------------------------- //
// Контракт
// --------------------------------------------------------------------------- //
export type ReviewPlatform = 'yandex' | '2gis';

const PLATFORM_LABEL: Record<ReviewPlatform, string> = { yandex: 'Яндекс Карты', '2gis': '2ГИС' };

type PlatformFilter = 'all' | ReviewPlatform;

const PLATFORM_FILTERS: readonly { readonly id: PlatformFilter; readonly label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'yandex', label: 'Яндекс' },
  { id: '2gis', label: '2ГИС' },
];

/** Подпись кнопки-заглушки вынесена в константу: меняется в одном месте. */
const REPLY_BUTTON_LABEL = 'Ответить с помощью AI';

// --------------------------------------------------------------------------- //
// Помощники
// --------------------------------------------------------------------------- //
const dateTimeFmt = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'long', timeStyle: 'short' });
const shortDateFmt = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' });

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : dateTimeFmt.format(d);
}

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : shortDateFmt.format(d);
}

function clampRating(value: number): number {
  return Math.max(1, Math.min(5, Math.round(value)));
}

function Stars({ value }: { readonly value: number }) {
  const rating = clampRating(value);
  return (
    <span role="img" aria-label={`Оценка ${rating} из 5`} className="inline-flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          aria-hidden="true"
          className={`h-3.5 w-3.5 ${n <= rating ? 'fill-current text-neutral-900' : 'text-neutral-300'}`}
        />
      ))}
    </span>
  );
}

function getPlatformLabel(platform: string | null): string {
  if (platform === 'yandex' || platform === '2gis') return PLATFORM_LABEL[platform];
  return platform ?? 'Площадка не указана';
}

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900';

// --------------------------------------------------------------------------- //
// Компонент
// --------------------------------------------------------------------------- //
export function ReviewsDashboard() {
  const { user } = useAuth();
  const companyId = user?.tenant_id ?? null;
  const [reviews, setReviews] = useState<SanitizedReview[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [platform, setPlatform] = useState<PlatformFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileDetail, setMobileDetail] = useState(false);
  const [replyNoticeFor, setReplyNoticeFor] = useState<string | null>(null);
  const itemRefs = useRef(new Map<string, HTMLButtonElement>());

  useEffect(() => {
    if (companyId === null) {
      setReviews([]);
      setError('Не удалось определить компанию для загрузки отзывов.');
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void fetchReviews(companyId, platform === 'all' ? null : platform, controller.signal)
      .then(setReviews)
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : 'Не удалось загрузить отзывы.');
        setReviews([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [companyId, platform]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return [...reviews]
      .filter((r) => q === '' || r.text.toLowerCase().includes(q) || (r.author_display ?? '').toLowerCase().includes(q))
      .sort((a, b) => (b.published_at ?? '').localeCompare(a.published_at ?? ''));
  }, [reviews, query]);

  const selected = visible.find((r) => r.id === selectedId) ?? visible[0] ?? null;

  function select(id: string): void {
    setSelectedId(id);
    setMobileDetail(true);
  }

  function onListKeyDown(event: KeyboardEvent<HTMLUListElement>): void {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    const index = visible.findIndex((r) => r.id === selected?.id);
    const next = visible[event.key === 'ArrowDown' ? Math.min(index + 1, visible.length - 1) : Math.max(index - 1, 0)];
    if (next === undefined) return;
    setSelectedId(next.id);
    itemRefs.current.get(next.id)?.focus();
  }

  return (
    <div className="flex h-screen min-h-[560px] w-full bg-white text-neutral-900">
      {/* Сайдбар: список отзывов */}
      <aside
        aria-label="Список отзывов"
        className={`${mobileDetail ? 'hidden' : 'flex'} w-full shrink-0 flex-col border-r border-neutral-200 md:flex md:w-96`}
      >
        <div className="border-b border-neutral-200 p-4">
          <div className="flex items-baseline justify-between">
            <h1 className="text-base font-semibold">Отзывы</h1>
            <span className="text-xs tabular-nums text-neutral-500" aria-live="polite">
              {visible.length} из {reviews.length}
            </span>
          </div>

          <label className="relative mt-3 block">
            <span className="sr-only">Поиск по тексту и автору</span>
            <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-neutral-400" />
            <input
              type="search"
              value={query}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
              placeholder="Поиск по тексту и автору"
              className={`h-9 w-full rounded-sm border border-neutral-300 bg-white pl-8 pr-2 text-sm placeholder:text-neutral-400 ${FOCUS}`}
            />
          </label>

          <div role="group" aria-label="Фильтр по площадке" className="mt-3 flex gap-1">
            {PLATFORM_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                aria-pressed={platform === f.id}
                onClick={() => setPlatform(f.id)}
                className={`h-8 flex-1 rounded-sm border text-sm ${FOCUS} ${
                  platform === f.id
                    ? 'border-neutral-900 bg-neutral-900 text-white'
                    : 'border-neutral-300 text-neutral-700 hover:bg-neutral-100'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div role="status" className="flex flex-1 items-center justify-center p-8 text-sm text-neutral-500">
            Загружаем отзывы…
          </div>
        ) : error !== null ? (
          <div role="alert" className="flex flex-1 items-center justify-center p-8 text-center text-sm text-red-700">
            {error}
          </div>
        ) : visible.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center text-sm text-neutral-500">
            <Inbox aria-hidden="true" className="h-6 w-6" />
            Отзывы не найдены. Измените запрос или фильтр.
          </div>
        ) : (
          <ul onKeyDown={onListKeyDown} className="flex-1 divide-y divide-neutral-200 overflow-y-auto">
            {visible.map((review) => {
              const active = review.id === selected?.id;
              return (
                <li key={review.id}>
                  <button
                    type="button"
                    ref={(el: HTMLButtonElement | null) => {
                      if (el) itemRefs.current.set(review.id, el);
                      else itemRefs.current.delete(review.id);
                    }}
                    onClick={() => select(review.id)}
                    aria-current={active ? 'true' : undefined}
                    className={`block w-full border-l-2 px-4 py-3 text-left ${FOCUS} ${
                      active ? 'border-neutral-900 bg-neutral-100' : 'border-transparent hover:bg-neutral-50'
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">{review.author_display ?? 'Анонимный клиент'}</span>
                      {review.published_at !== null && (
                        <time dateTime={review.published_at} className="shrink-0 text-xs text-neutral-500">
                          {formatShortDate(review.published_at)}
                        </time>
                      )}
                    </span>
                    <span className="mt-1 flex items-center gap-2">
                      <Stars value={review.rating} />
                      <span className="text-xs text-neutral-500">{getPlatformLabel(review.platform)}</span>
                    </span>
                    <span className="mt-1.5 line-clamp-2 block text-sm text-neutral-600">{review.text}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </aside>

      {/* Главное окно: детали */}
      <main className={`${mobileDetail ? 'flex' : 'hidden'} min-w-0 flex-1 flex-col overflow-y-auto md:flex`}>
        {selected === null ? (
          <div className="flex flex-1 items-center justify-center p-8 text-sm text-neutral-500">
            Выберите отзыв в списке слева.
          </div>
        ) : (
          <article aria-labelledby="review-title" className="mx-auto w-full max-w-3xl p-6 md:p-10">
            <button
              type="button"
              onClick={() => setMobileDetail(false)}
              className={`mb-4 inline-flex items-center gap-1.5 text-sm text-neutral-600 hover:text-neutral-900 md:hidden ${FOCUS}`}
            >
              <ArrowLeft aria-hidden="true" className="h-4 w-4" />
              К списку
            </button>

            <header className="border-b border-neutral-200 pb-5">
              <div className="flex flex-wrap items-center gap-3">
                <span className="inline-flex h-5 items-center rounded-sm border border-neutral-300 px-1.5 text-[11px] font-medium uppercase tracking-wide text-neutral-700">
                  {getPlatformLabel(selected.platform)}
                </span>
                <Stars value={selected.rating} />
                <span className="text-sm tabular-nums text-neutral-500">{clampRating(selected.rating)}/5</span>
              </div>
              <h2 id="review-title" className="mt-3 text-xl font-semibold">
                {selected.author_display ?? 'Анонимный клиент'}
              </h2>
              {selected.published_at !== null && (
                <time dateTime={selected.published_at} className="mt-1 block text-sm text-neutral-500">
                  {formatDateTime(selected.published_at)}
                </time>
              )}
            </header>

            <section aria-label="Текст отзыва" className="py-6">
              <p className="whitespace-pre-line text-base leading-7 text-neutral-800">{selected.text}</p>
            </section>

            <dl className="grid grid-cols-1 gap-4 border-y border-neutral-200 py-5 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs uppercase tracking-wide text-neutral-500">ID отзыва</dt>
                <dd className="mt-1 break-all font-mono text-neutral-800">{selected.id}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-neutral-500">Хэш автора</dt>
                <dd className="mt-1 break-all font-mono text-neutral-800">{selected.author_hash ?? 'Не указан'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-neutral-500">Площадка</dt>
                <dd className="mt-1 text-neutral-800">{getPlatformLabel(selected.platform)}</dd>
              </div>
            </dl>

            <section aria-label="Ответ на отзыв" className="pt-6">
              <h3 className="text-sm font-semibold">Ответ на отзыв</h3>
              <p className="mt-1 text-sm text-neutral-500">
                Подготовьте черновик ответа. Публикация выполняется только после проверки менеджером.
              </p>
              <button
                type="button"
                onClick={() => setReplyNoticeFor(selected.id)}
                className={`mt-4 inline-flex h-9 items-center gap-2 rounded-sm bg-neutral-900 px-4 text-sm font-medium text-white hover:bg-neutral-700 ${FOCUS}`}
              >
                <Sparkles aria-hidden="true" className="h-4 w-4" />
                {REPLY_BUTTON_LABEL}
              </button>
              <p role="status" className="mt-3 min-h-5 text-sm text-neutral-600">
                {replyNoticeFor === selected.id ? 'Функция в разработке: генерация ответа будет подключена позже.' : ''}
              </p>
            </section>
          </article>
        )}
      </main>
    </div>
  );
}

export default ReviewsDashboard;
