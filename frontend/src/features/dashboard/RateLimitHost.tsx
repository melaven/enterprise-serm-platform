import { useEffect, useState, useSyncExternalStore } from 'react';

import { rateLimitStore } from '@/api/rateLimit';

/**
 * Таймер для HTTP 429. Монтируется ОДИН раз в корне (не зависит от роутера).
 * Не модалка: интерфейс остаётся живым, а запросы сами подождут конец паузы.
 * Точная лимитная индикация на непрозрачной брендовой поверхности.
 */
export function RateLimitHost() {
  const info = useSyncExternalStore(
    rateLimitStore.subscribe,
    rateLimitStore.getSnapshot,
    rateLimitStore.getServerSnapshot,
  );
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!info) return;
    setNow(Date.now());
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= info.retryAt) rateLimitStore.dismiss();
    }, 200);
    return () => clearInterval(id);
  }, [info]);

  if (!info) return null;

  const remaining = Math.max(0, info.retryAt - now);
  const seconds = Math.ceil(remaining / 1000);
  const fraction = info.durationMs > 0 ? Math.min(1, remaining / info.durationMs) : 0;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 right-4 z-[60] w-[calc(100%-2rem)] max-w-sm rounded-sm border border-plum-700 bg-plum-900 p-4 text-white sm:bottom-6 sm:right-6 sm:w-[calc(100%-3rem)] sm:p-6"
    >
      <p className="sr-only">Слишком много запросов. Повторим автоматически.</p>
      <div aria-hidden="true">
        <p className="text-xs font-medium uppercase tracking-wider text-white/60">
          429 · Слишком много запросов
        </p>
        <div className="mt-3 flex flex-col gap-2 sm:mt-4 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
          <p className="text-xs text-white/80 sm:text-sm">Повторим автоматически через</p>
          <p className="font-mono text-3xl font-medium leading-none tabular-nums sm:text-4xl">
            {seconds}
            <span className="ml-1 text-sm font-normal text-white/60">с</span>
          </p>
        </div>
        <div className="mt-4 h-1 rounded-sm bg-white/15 sm:mt-5">
          <div
            className="h-full rounded-sm bg-lime transition-[width] duration-200 ease-linear"
            style={{ width: `${fraction * 100}%` }}
          />
        </div>
        {info.correlationId ? (
          <p className="mt-3 font-mono text-xs text-white/40 sm:mt-4">ID: {info.correlationId}</p>
        ) : null}
      </div>
    </div>
  );
}
