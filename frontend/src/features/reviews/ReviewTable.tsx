import { useMemo, useState } from 'react';

export type TablePlatform = 'yandex' | '2gis';
export type ReviewStatus = 'new' | 'analyzed' | 'moderation' | 'published';

export interface ReviewRow {
  readonly external_id: string;
  readonly platform: TablePlatform;
  readonly author_hash: `usr_${string}`;
  /** 1–5 */
  readonly rating: number;
  /** ISO 8601 */
  readonly published_at: string;
  readonly status: ReviewStatus;
}

const PLATFORM_LABEL: Record<TablePlatform, string> = { yandex: 'Яндекс Карты', '2gis': '2ГИС' };

// Статусы различаются начертанием, а не цветом: контур / серая заливка / тёмная заливка.
const STATUS: Record<ReviewStatus, { readonly label: string; readonly cls: string }> = {
  new: { label: 'Новый', cls: 'border-gray-300 bg-white text-gray-700' },
  analyzed: { label: 'Проанализирован', cls: 'border-gray-300 bg-gray-100 text-gray-800' },
  moderation: { label: 'На модерации', cls: 'border-gray-500 bg-gray-200 text-gray-900' },
  published: { label: 'Опубликован', cls: 'border-gray-900 bg-gray-900 text-white' },
};

export const MOCK_REVIEW_ROWS: readonly ReviewRow[] = [
  { external_id: 'ya-90412', platform: 'yandex', author_hash: 'usr_8f3a21c9', rating: 1, published_at: '2026-10-29T18:42:00Z', status: 'new' },
  { external_id: '2g-55120', platform: '2gis', author_hash: 'usr_41b7e0d2', rating: 5, published_at: '2026-10-29T11:05:00Z', status: 'published' },
  { external_id: 'ya-90377', platform: 'yandex', author_hash: 'usr_c20d9a77', rating: 3, published_at: '2026-10-28T20:15:00Z', status: 'analyzed' },
  { external_id: '2g-55087', platform: '2gis', author_hash: 'usr_6e1f43ab', rating: 2, published_at: '2026-10-28T13:30:00Z', status: 'moderation' },
  { external_id: 'ya-90301', platform: 'yandex', author_hash: 'usr_0a95d6f1', rating: 4, published_at: '2026-10-27T09:48:00Z', status: 'published' },
  { external_id: '2g-55002', platform: '2gis', author_hash: 'usr_9d2c7b30', rating: 5, published_at: '2026-10-26T19:20:00Z', status: 'analyzed' },
  { external_id: 'ya-90255', platform: 'yandex', author_hash: 'usr_b7e48c15', rating: 1, published_at: '2026-10-25T17:12:00Z', status: 'moderation' },
  { external_id: '2g-54931', platform: '2gis', author_hash: 'usr_25a0e9c4', rating: 3, published_at: '2026-10-24T08:40:00Z', status: 'new' },
  { external_id: 'ya-90190', platform: 'yandex', author_hash: 'usr_f14b8a02', rating: 4, published_at: '2026-10-23T21:05:00Z', status: 'analyzed' },
  { external_id: '2g-54870', platform: '2gis', author_hash: 'usr_73c6d1e8', rating: 5, published_at: '2026-10-22T12:25:00Z', status: 'published' },
  { external_id: 'ya-90102', platform: 'yandex', author_hash: 'usr_d8e21f56', rating: 2, published_at: '2026-10-21T15:50:00Z', status: 'new' },
  { external_id: '2g-54802', platform: '2gis', author_hash: 'usr_1c7a90be', rating: 4, published_at: '2026-10-20T10:10:00Z', status: 'analyzed' },
];

const dateFmt = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : dateFmt.format(d);
}

function RatingCell({ value }: { readonly value: number }) {
  const rating = Math.max(1, Math.min(5, Math.round(value)));
  return (
    <span className="inline-flex items-center gap-2" role="img" aria-label={`Рейтинг ${rating} из 5`}>
      <span aria-hidden="true" className="inline-flex gap-0.5">
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className={`h-2 w-2.5 rounded-sm ${n <= rating ? 'bg-gray-900' : 'bg-gray-200'}`} />
        ))}
      </span>
      <span aria-hidden="true" className="tabular-nums text-gray-700">
        {rating}/5
      </span>
    </span>
  );
}

type SortKey = 'published_at' | 'rating';
type SortDir = 'asc' | 'desc';
type SortState = { key: SortKey; dir: SortDir };

const TH = 'whitespace-nowrap px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-gray-500';
const TD = 'px-3 py-2 align-middle';
const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-gray-900';

interface SortableThProps {
  readonly column: SortKey;
  readonly label: string;
  readonly sort: SortState;
  readonly onSort: (key: SortKey) => void;
}

function SortableTh({ column, label, sort, onSort }: SortableThProps) {
  const active = sort.key === column;
  return (
    <th scope="col" className={TH} aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" onClick={() => onSort(column)} className={`inline-flex items-center gap-1 uppercase tracking-wide ${FOCUS}`}>
        {label}
        <span aria-hidden="true" className={active ? 'text-gray-900' : 'text-gray-300'}>
          {active && sort.dir === 'asc' ? '▲' : '▼'}
        </span>
      </button>
    </th>
  );
}

interface ReviewTableProps {
  readonly reviews?: readonly ReviewRow[];
  readonly onSelect?: (review: ReviewRow) => void;
}

/** Таблица отзывов: Дата, Платформа, Автор-хэш, Рейтинг, Статус. Сортировка по дате и рейтингу. */
export function ReviewTable({ reviews = MOCK_REVIEW_ROWS, onSelect }: ReviewTableProps) {
  const [sort, setSort] = useState<SortState>({ key: 'published_at', dir: 'desc' });

  const rows = useMemo(() => {
    const sign = sort.dir === 'asc' ? 1 : -1;
    return [...reviews].sort((a, b) => {
      const diff = sort.key === 'rating' ? a.rating - b.rating : a.published_at.localeCompare(b.published_at);
      return diff * sign || a.external_id.localeCompare(b.external_id);
    });
  }, [reviews, sort]);

  function toggle(key: SortKey): void {
    setSort((prev) => (prev.key === key ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }));
  }

  return (
    <div className="overflow-x-auto rounded-sm border border-gray-200 bg-white">
      <table className="w-full border-collapse text-sm">
        <caption className="sr-only">Отзывы: {rows.length}</caption>
        <thead className="border-b border-gray-200 bg-gray-50">
          <tr>
            <SortableTh column="published_at" label="Дата" sort={sort} onSort={toggle} />
            <th scope="col" className={TH}>Платформа</th>
            <th scope="col" className={TH}>Автор-хэш</th>
            <SortableTh column="rating" label="Рейтинг" sort={sort} onSort={toggle} />
            <th scope="col" className={TH}>Статус</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-3 py-8 text-center text-gray-500">
                Отзывов пока нет.
              </td>
            </tr>
          ) : (
            rows.map((review) => (
              <tr
                key={review.external_id}
                onClick={onSelect ? () => onSelect(review) : undefined}
                className={`hover:bg-gray-50 ${onSelect ? 'cursor-pointer' : ''}`}
              >
                <td className={`${TD} whitespace-nowrap tabular-nums text-gray-700`}>
                  <time dateTime={review.published_at}>{formatDate(review.published_at)}</time>
                </td>
                <td className={`${TD} whitespace-nowrap text-gray-900`}>{PLATFORM_LABEL[review.platform]}</td>
                <td className={`${TD} font-mono text-xs text-gray-700`}>
                  <span title={review.author_hash}>{review.author_hash}</span>
                </td>
                <td className={`${TD} whitespace-nowrap`}>
                  <RatingCell value={review.rating} />
                </td>
                <td className={`${TD} whitespace-nowrap`}>
                  <span className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs ${STATUS[review.status].cls}`}>
                    {STATUS[review.status].label}
                  </span>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export default ReviewTable;
