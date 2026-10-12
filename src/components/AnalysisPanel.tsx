import { Activity, Hourglass, MessageSquareText, ShieldAlert, type LucideIcon } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

// ── Типы данных ──────────────────────────────────────────────────────────────

export interface TimelinePoint {
  /** Начало интервала, YYYY-MM-DD */
  date: string;
  count: number;
}

export interface SentimentDistribution {
  positive: number;
  neutral: number;
  negative: number;
  unclassified: number;
}

export interface AnalysisData {
  total_reviews: number;
  average_rating: number | null;
  sentiment: SentimentDistribution;
  timeline: TimelinePoint[];
  /** Отзывы с is_critical=true. null: бэкенд не прислал, покажем «—», а не ложный 0. */
  critical_reviews: number | null;
  /** Отзывы с ai_pending=true (ждут AI-разметки). null: не прислано. */
  ai_pending: number | null;
  /** Подпись периода, например «30 дней». */
  period?: string;
}

export interface AnalysisPanelProps {
  /** null + isLoading: показываем скелетон; null без загрузки: панель не рисуем. */
  data: AnalysisData | null;
  isLoading?: boolean;
  online: boolean;
  onStartParsing: () => void;
  isParsing?: boolean;
  className?: string;
}

// ── Расчёты ──────────────────────────────────────────────────────────────────

/**
 * Индекс тональности: (позитив − негатив) / размеченные × 100, от −100 до +100.
 * null, если размеченных отзывов нет.
 */
export function sentimentIndex(s: SentimentDistribution): number | null {
  const classified = s.positive + s.neutral + s.negative;
  return classified > 0 ? Math.round(((s.positive - s.negative) / classified) * 100) : null;
}

const pct = (part: number, whole: number): number => (whole > 0 ? Math.round((part / whole) * 100) : 0);
const nf = new Intl.NumberFormat('ru-RU');
const LABEL = 'text-xs font-medium uppercase tracking-wider text-zinc-400';

// ── KPI-карточка ─────────────────────────────────────────────────────────────

type Tone = 'neutral' | 'positive' | 'critical';

const VALUE_TONE: Record<Tone, string> = {
  neutral: 'text-white',
  positive: 'text-lime',
  critical: 'text-danger',
};
const ICON_TONE: Record<Tone, string> = {
  neutral: 'text-zinc-500',
  positive: 'text-lime',
  critical: 'text-danger',
};

interface KpiCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
}

function KpiCard({ icon: Icon, label, value, hint, tone = 'neutral' }: KpiCardProps) {
  return (
    <div className={cn('border border-zinc-800 p-6', tone === 'critical' && 'border-l-2 border-l-danger')}>
      <div className="flex items-center justify-between gap-4">
        <dt className={LABEL}>{label}</dt>
        <Icon className={cn('size-4 shrink-0', ICON_TONE[tone])} strokeWidth={1.5} aria-hidden="true" />
      </div>
      <dd className="mt-6">
        <span
          className={cn(
            'block text-5xl font-medium leading-none tracking-tight tabular-nums',
            value === '—' ? 'text-zinc-600' : VALUE_TONE[tone],
          )}
        >
          {value}
        </span>
        {hint ? <span className="mt-3 block text-xs text-zinc-500">{hint}</span> : null}
      </dd>
    </div>
  );
}

// ── График динамики ──────────────────────────────────────────────────────────

function Timeline({ points }: { points: TimelinePoint[] }) {
  const W = 800;
  const H = 200;
  const PAD = 12;

  if (points.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center border border-zinc-800 text-xs uppercase tracking-wider text-zinc-600">
        Нет данных за период
      </div>
    );
  }

  const max = Math.max(...points.map((p) => p.count), 1);
  const step = points.length > 1 ? (W - PAD * 2) / (points.length - 1) : 0;
  const coords = points.map((p, i) => ({
    x: points.length > 1 ? PAD + i * step : W / 2,
    y: H - PAD - (p.count / max) * (H - PAD * 2),
    ...p,
  }));
  const path = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`).join(' ');

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-[200px] w-full"
      role="img"
      aria-label="Динамика количества отзывов"
      preserveAspectRatio="none"
    >
      {[0.25, 0.5, 0.75].map((t) => (
        <line
          key={t}
          x1={0}
          x2={W}
          y1={H * t}
          y2={H * t}
          className="stroke-zinc-900"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
      ))}
      <path
        d={path}
        fill="none"
        className="stroke-zinc-500"
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
      {coords.length <= 60 &&
        coords.map((c) => (
          <rect key={c.date} x={c.x - 3} y={c.y - 3} width={6} height={6} className="fill-lime">
            <title>{`${c.date}: ${c.count}`}</title>
          </rect>
        ))}
    </svg>
  );
}

// ── Скелетон ─────────────────────────────────────────────────────────────────

function AnalysisSkeleton() {
  return (
    <div aria-busy="true" aria-label="Загрузка аналитики">
      <div className="mt-8 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="border border-zinc-800 p-6">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-6 h-12 w-28" />
            <Skeleton className="mt-3 h-3 w-36" />
          </div>
        ))}
      </div>
      <div className="mt-8 border border-zinc-800 p-8">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="mt-6 h-[200px] w-full" />
      </div>
      <div className="mt-8 border border-zinc-800 p-8">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-6 h-3 w-full" />
      </div>
    </div>
  );
}

// ── Панель ───────────────────────────────────────────────────────────────────

export function AnalysisPanel({
  data,
  isLoading = false,
  online,
  onStartParsing,
  isParsing = false,
  className,
}: AnalysisPanelProps) {
  if (!data && !isLoading) return null;
  const s: SentimentDistribution = data?.sentiment ?? { positive: 0, neutral: 0, negative: 0, unclassified: 0 };
  const classified = s.positive + s.neutral + s.negative;
  const posPct = pct(s.positive, classified);
  const neuPct = pct(s.neutral, classified);
  const negPct = classified > 0 ? Math.max(0, 100 - posPct - neuPct) : 0;

  const index = sentimentIndex(s);
  const indexTone: Tone = index !== null && index > 0 ? 'positive' : 'neutral';
  const critical = data?.critical_reviews ?? null;

  return (
    <section
      aria-labelledby="analysis-title"
      className={cn('border border-zinc-800 bg-zinc-950 p-8', className)}
    >
      <header className="flex flex-wrap items-center justify-between gap-6">
        <div>
          <h2 id="analysis-title" className={LABEL}>
            Аналитика{data?.period ? ` · ${data.period}` : ''}
          </h2>
          <p className="mt-3 flex items-center gap-2 text-xs uppercase tracking-wider text-zinc-400">
            <span aria-hidden="true" className={cn('size-2', online ? 'bg-lime' : 'bg-zinc-700')} />
            {online ? 'Онлайн' : 'Офлайн'}
          </p>
        </div>
        <Button onClick={onStartParsing} disabled={isParsing}>
          {isParsing ? 'Сбор идёт…' : 'Запустить сбор'}
        </Button>
      </header>

      {!data ? (
        <AnalysisSkeleton />
      ) : (
        <>
      <dl className="mt-8 grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          icon={MessageSquareText}
          label="Всего отзывов"
          value={nf.format(data.total_reviews)}
          hint={data.average_rating === null ? undefined : `Средняя оценка ${data.average_rating.toFixed(1)}`}
        />
        <KpiCard
          icon={Activity}
          label="Индекс тональности"
          value={index === null ? '—' : `${index > 0 ? '+' : ''}${index}`}
          hint="Позитив минус негатив, от −100 до +100"
          tone={indexTone}
        />
        <KpiCard
          icon={ShieldAlert}
          label="Критичные проблемы"
          value={critical === null ? '—' : nf.format(critical)}
          hint={critical === null ? undefined : critical > 0 ? 'Требуют реакции' : 'Не обнаружено'}
          tone={critical !== null && critical > 0 ? 'critical' : 'neutral'}
        />
        <KpiCard
          icon={Hourglass}
          label="Ждут AI-разметки"
          value={data.ai_pending === null ? '—' : nf.format(data.ai_pending)}
          hint="Дообработаются автоматически"
        />
      </dl>

      <div className="mt-8 border border-zinc-800 p-8">
        <p className={LABEL}>Динамика отзывов</p>
        <div className="mt-6">
          <Timeline points={data.timeline} />
        </div>
      </div>

      <div className="mt-8 border border-zinc-800 p-8">
        <p className={LABEL}>Тональность</p>
        <div
          className="mt-6 flex h-3 w-full bg-zinc-900"
          role="img"
          aria-label={`Позитив ${posPct}%, нейтрально ${neuPct}%, негатив ${negPct}%`}
        >
          <div className="h-full bg-lime" style={{ width: `${posPct}%` }} />
          <div className="h-full bg-zinc-600" style={{ width: `${neuPct}%` }} />
          <div className="h-full bg-plum" style={{ width: `${negPct}%` }} />
        </div>
        <ul className="mt-6 grid grid-cols-2 gap-6 text-xs uppercase tracking-wider text-zinc-400 md:grid-cols-4">
          {(
            [
              ['Позитив', s.positive, 'bg-lime'],
              ['Нейтрально', s.neutral, 'bg-zinc-600'],
              ['Негатив', s.negative, 'bg-plum'],
              ['Не размечено', s.unclassified, 'bg-zinc-800'],
            ] as const
          ).map(([name, n, dot]) => (
            <li key={name} className="flex items-center gap-3">
              <span aria-hidden="true" className={cn('size-2 shrink-0', dot)} />
              <span>{name}</span>
              <span className="ml-auto text-white tabular-nums">{nf.format(n)}</span>
            </li>
          ))}
        </ul>
      </div>
        </>
      )}
    </section>
  );
}
