import { useMemo, useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react';
import { ArrowLeft, Inbox, Search, Sparkles, Star } from 'lucide-react';

// --------------------------------------------------------------------------- //
// Контракт
// --------------------------------------------------------------------------- //
export type ReviewPlatform = 'yandex' | '2gis';

export interface SanitizedReview {
  readonly external_id: string;
  readonly platform: ReviewPlatform;
  readonly author_hash: `usr_${string}`;
  readonly author_display: string;
  readonly text: string;
  /** 1–5 */
  readonly rating: number;
  /** ISO 8601 */
  readonly published_at: string;
}

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
// Мок-данные
// --------------------------------------------------------------------------- //
export const MOCK_REVIEWS: readonly SanitizedReview[] = [
  {
    external_id: 'ya-90412',
    platform: 'yandex',
    author_hash: 'usr_8f3a21c9',
    author_display: 'Гость 4821',
    text: 'Ждали заказ больше часа, суп принесли холодным, а администратор только развёл руками. Больше не придём.',
    rating: 1,
    published_at: '2026-10-28T18:42:00Z',
  },
  {
    external_id: '2g-55120',
    platform: '2gis',
    author_hash: 'usr_41b7e0d2',
    author_display: 'Клиент M.',
    text: 'Отличное место для семейного ужина. Быстрая подача, вежливый персонал, чисто. Рекомендую детское меню.',
    rating: 5,
    published_at: '2026-10-28T11:05:00Z',
  },
  {
    external_id: 'ya-90377',
    platform: 'yandex',
    author_hash: 'usr_c20d9a77',
    author_display: 'Гость 1093',
    text: 'В целом нормально. Кухня хорошая, но в зале шумно, а обслуживание в пятницу вечером заметно медленнее.',
    rating: 3,
    published_at: '2026-10-27T20:15:00Z',
  },
  {
    external_id: '2g-55087',
    platform: '2gis',
    author_hash: 'usr_6e1f43ab',
    author_display: 'Клиент А.',
    text: 'Неверно посчитали счёт, разбирались около двадцати минут. Блюда понравились, но осадок остался.',
    rating: 2,
    published_at: '2026-10-27T13:30:00Z',
  },
  {
    external_id: 'ya-90301',
    platform: 'yandex',
    author_hash: 'usr_0a95d6f1',
    author_display: 'Гость 7710',
    text: 'Были на деловом обеде: быстро, вкусно, цены адекватные. Удобная парковка рядом.',
    rating: 4,
    published_at: '2026-10-26T09:48:00Z',
  },
  {
    external_id: '2g-55002',
    platform: '2gis',
    author_hash: 'usr_9d2c7b30',
    author_display: 'Клиент Е.',
    text: 'Лучшая паста в районе. Горячо, порция большая, персонал приветливый.',
    rating: 5,
    published_at: '2026-10-25T19:20:00Z',
  },
  {
    external_id: 'ya-90255',
    platform: 'yandex',
    author_hash: 'usr_b7e48c15',
    author_display: 'Гость 3356',
    text: 'Столик, который мы бронировали, оказался занят. Подождали сорок минут, никаких извинений не услышали.',
    rating: 1,
    published_at: '2026-10-24T17:12:00Z',
  },
  {
    external_id: '2g-54931',
    platform: '2gis',
    author_hash: 'usr_25a0e9c4',
    author_display: 'Клиент Д.',
    text: 'Обычное кафе. Ничего особенного, но и претензий нет. Кофе приготовили хорошо.',
    rating: 3,
    published_at: '2026-10-23T08:40:00Z',
  },
  {
    external_id: 'ya-90190',
    platform: 'yandex',
    author_hash: 'usr_f14b8a02',
    author_display: 'Гость 5204',
    text: 'Приятная атмосфера, живая музыка по выходным. Единственный минус — ограниченный выбор десертов.',
    rating: 4,
    published_at: '2026-10-22T21:05:00Z',
  },
  {
    external_id: '2g-54870',
    platform: '2gis',
    author_hash: 'usr_73c6d1e8',
    author_display: 'Клиент С.',
    text: 'Заказывали доставку: привезли вовремя, упаковка аккуратная, всё горячее. Спасибо.',
    rating: 5,
    published_at: '2026-10-21T12:25:00Z',
  },
];

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

function PlatformBadge({ platform }: { readonly platform: ReviewPlatform }) {
  return (
    <span className="inline-flex h-5 items-center rounded-sm border border-neutral-300 px-1.5 text-[11px] font-medium uppercase tracking-wide text-neutral-700">
      {PLATFORM_LABEL[platform]}
    </span>
  );
}

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900';

// --------------------------------------------------------------------------- //
// Компонент
// --------------------------------------------------------------------------- //
interface ReviewsDashboardProps {
  readonly reviews?: readonly SanitizedReview[];
}

export function ReviewsDashboardMock({ reviews = MOCK_REVIEWS }: ReviewsDashboardProps) {
  const [query, setQuery] = useState('');
  const [platform, setPlatform] = useState<PlatformFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileDetail, setMobileDetail] = useState(false);
  const [replyNoticeFor, setReplyNoticeFor] = useState<string | null>(null);
  const itemRefs = useRef(new Map<string, HTMLButtonElement>());

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return [...reviews]
      .filter((r) => platform === 'all' || r.platform === platform)
      .filter((r) => q === '' || r.text.toLowerCase().includes(q) || r.author_display.toLowerCase().includes(q))
      .sort((a, b) => b.published_at.localeCompare(a.published_at));
  }, [reviews, query, platform]);

  const selected = visible.find((r) => r.external_id === selectedId) ?? visible[0] ?? null;

  function select(id: string): void {
    setSelectedId(id);
    setMobileDetail(true);
  }

  function onListKeyDown(event: KeyboardEvent<HTMLUListElement>): void {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    const index = visible.findIndex((r) => r.external_id === selected?.external_id);
    const next = visible[event.key === 'ArrowDown' ? Math.min(index + 1, visible.length - 1) : Math.max(index - 1, 0)];
    if (next === undefined) return;
    setSelectedId(next.external_id);
    itemRefs.current.get(next.external_id)?.focus();
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

        {visible.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center text-sm text-neutral-500">
            <Inbox aria-hidden="true" className="h-6 w-6" />
            Отзывы не найдены. Измените запрос или фильтр.
          </div>
        ) : (
          <ul onKeyDown={onListKeyDown} className="flex-1 divide-y divide-neutral-200 overflow-y-auto">
            {visible.map((review) => {
              const active = review.external_id === selected?.external_id;
              return (
                <li key={review.external_id}>
                  <button
                    type="button"
                    ref={(el: HTMLButtonElement | null) => {
                      if (el) itemRefs.current.set(review.external_id, el);
                      else itemRefs.current.delete(review.external_id);
                    }}
                    onClick={() => select(review.external_id)}
                    aria-current={active ? 'true' : undefined}
                    className={`block w-full border-l-2 px-4 py-3 text-left ${FOCUS} ${
                      active ? 'border-neutral-900 bg-neutral-100' : 'border-transparent hover:bg-neutral-50'
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">{review.author_display}</span>
                      <time dateTime={review.published_at} className="shrink-0 text-xs text-neutral-500">
                        {formatShortDate(review.published_at)}
                      </time>
                    </span>
                    <span className="mt-1 flex items-center gap-2">
                      <Stars value={review.rating} />
                      <span className="text-xs text-neutral-500">{PLATFORM_LABEL[review.platform]}</span>
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
                <PlatformBadge platform={selected.platform} />
                <Stars value={selected.rating} />
                <span className="text-sm tabular-nums text-neutral-500">{clampRating(selected.rating)}/5</span>
              </div>
              <h2 id="review-title" className="mt-3 text-xl font-semibold">
                {selected.author_display}
              </h2>
              <time dateTime={selected.published_at} className="mt-1 block text-sm text-neutral-500">
                {formatDateTime(selected.published_at)}
              </time>
            </header>

            <section aria-label="Текст отзыва" className="py-6">
              <p className="whitespace-pre-line text-base leading-7 text-neutral-800">{selected.text}</p>
            </section>

            <dl className="grid grid-cols-1 gap-4 border-y border-neutral-200 py-5 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs uppercase tracking-wide text-neutral-500">ID отзыва</dt>
                <dd className="mt-1 break-all font-mono text-neutral-800">{selected.external_id}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-neutral-500">Хэш автора</dt>
                <dd className="mt-1 break-all font-mono text-neutral-800">{selected.author_hash}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-neutral-500">Площадка</dt>
                <dd className="mt-1 text-neutral-800">{PLATFORM_LABEL[selected.platform]}</dd>
              </div>
            </dl>

            <section aria-label="Ответ на отзыв" className="pt-6">
              <h3 className="text-sm font-semibold">Ответ на отзыв</h3>
              <p className="mt-1 text-sm text-neutral-500">
                Подготовьте черновик ответа. Публикация выполняется только после проверки менеджером.
              </p>
              <button
                type="button"
                onClick={() => setReplyNoticeFor(selected.external_id)}
                className={`mt-4 inline-flex h-9 items-center gap-2 rounded-sm bg-neutral-900 px-4 text-sm font-medium text-white hover:bg-neutral-700 ${FOCUS}`}
              >
                <Sparkles aria-hidden="true" className="h-4 w-4" />
                {REPLY_BUTTON_LABEL}
              </button>
              <p role="status" className="mt-3 min-h-5 text-sm text-neutral-600">
                {replyNoticeFor === selected.external_id ? 'Функция в разработке: генерация ответа будет подключена позже.' : ''}
              </p>
            </section>
          </article>
        )}
      </main>
    </div>
  );
}

export default ReviewsDashboardMock;
