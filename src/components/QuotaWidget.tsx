import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface QuotaCounter {
  used: number;
  limit: number;
}

export interface QuotaWidgetProps {
  llmTokens: QuotaCounter;
  reviewsParsed: QuotaCounter;
  /** YYYY-MM-DD (UTC): следующий сброс счётчиков */
  resetDate: string;
  onUpgrade?: () => void;
  /** Узкий режим для сайдбара: меньше отступы и кегль */
  compact?: boolean;
  className?: string;
}

const WARN_AT = 90;
const numberFmt = new Intl.NumberFormat('ru-RU');
const dateFmt = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
});

function usedPercent({ used, limit }: QuotaCounter): number {
  return limit <= 0 ? 100 : Math.round((used / limit) * 100);
}

function QuotaRow({
  label,
  unit,
  counter,
  compact,
}: {
  label: string;
  unit: string;
  counter: QuotaCounter;
  compact?: boolean;
}) {
  const pct = usedPercent(counter);
  const exhausted = counter.used >= counter.limit;
  const warning = !exhausted && pct >= WARN_AT;

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <span className="text-sm text-zinc-400">{label}</span>
        {exhausted ? (
          <span className="rounded-sm bg-plum px-2 py-1 text-xs font-semibold uppercase tracking-wider text-white">
            Лимит исчерпан
          </span>
        ) : warning ? (
          <span className="rounded-sm bg-lime px-2 py-1 text-xs font-semibold uppercase tracking-wider text-black">
            Порог {WARN_AT}%
          </span>
        ) : null}
      </div>

      <div className="mt-3 flex items-baseline gap-3">
        <span
          className={cn(
            'font-medium leading-none tracking-tight text-white tabular-nums',
            compact ? 'text-3xl' : 'text-5xl',
          )}
        >
          {numberFmt.format(counter.used)}
        </span>
        <span className={cn('text-zinc-500 tabular-nums', compact ? 'text-xs' : 'text-base')}>
          / {numberFmt.format(counter.limit)} {unit}
        </span>
      </div>

      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={counter.limit}
        aria-valuenow={Math.min(counter.used, counter.limit)}
        className="mt-5 h-1.5 w-full bg-zinc-900"
      >
        <div
          className={cn('h-full', exhausted ? 'bg-plum' : 'bg-lime')}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
      <div className="mt-2 text-right text-xs text-zinc-400 tabular-nums">{pct}%</div>
    </div>
  );
}

export function QuotaWidget({
  llmTokens,
  reviewsParsed,
  resetDate,
  onUpgrade,
  compact = false,
  className,
}: QuotaWidgetProps) {
  const needsUpgrade = llmTokens.used >= llmTokens.limit || reviewsParsed.used >= reviewsParsed.limit;

  return (
    <section aria-labelledby="quota-title" className={cn('border border-zinc-800 bg-zinc-950', compact ? 'p-6' : 'p-8', className)}>
      <h2 id="quota-title" className="text-xs font-medium uppercase tracking-wider text-zinc-400">
        Квоты и тариф
      </h2>

      <div className={cn(compact ? 'mt-6 space-y-6' : 'mt-10 space-y-10')}>
        <QuotaRow label="LLM-токены" unit="ток." counter={llmTokens} compact={compact} />
        <QuotaRow label="Разобрано отзывов" unit="отз." counter={reviewsParsed} compact={compact} />
      </div>

      <div
        className={cn(
          'flex items-end justify-between gap-4 border-t border-zinc-900 pt-6',
          compact ? 'mt-6 flex-wrap' : 'mt-10',
        )}
      >
        <div>
          <div className="text-xs font-medium uppercase tracking-wider text-zinc-400">Сброс счётчиков</div>
          <div className="mt-2 text-sm text-zinc-100">{dateFmt.format(new Date(resetDate))}</div>
        </div>
        {onUpgrade ? (
          <Button
            variant={needsUpgrade ? 'default' : 'outline'}
            size={compact ? 'sm' : 'default'}
            onClick={onUpgrade}
          >
            Сменить тариф
          </Button>
        ) : null}
      </div>
    </section>
  );
}
