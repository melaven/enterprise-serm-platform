/**
 * Глобальное состояние «слишком много запросов» (HTTP 429 + Retry-After).
 * Без зависимостей от React/axios: подписка через useSyncExternalStore, тесты в Node.
 */

/** Если бэкенд не прислал (или браузер скрыл CORS-ом) Retry-After. */
export const DEFAULT_RETRY_AFTER_S = 15;
const MAX_RETRY_AFTER_S = 3600;

/**
 * Retry-After: целое число секунд ИЛИ HTTP-date (RFC 9110). Возвращает секунды (1..3600)
 * или null, если значение не распознано. 0 и даты в прошлом превращаются в 1 с, чтобы не крутить цикл.
 */
export function parseRetryAfter(value: unknown, now: number = Date.now()): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.min(MAX_RETRY_AFTER_S, Math.max(1, Math.ceil(value)));
  }
  if (typeof value !== 'string') return null;
  const v = value.trim();
  if (/^\d+$/.test(v)) return Math.min(MAX_RETRY_AFTER_S, Math.max(1, Number(v)));
  const at = Date.parse(v);
  if (Number.isNaN(at)) return null;
  return Math.min(MAX_RETRY_AFTER_S, Math.max(1, Math.ceil((at - now) / 1000)));
}

export interface RateLimitInfo {
  /** Когда можно повторять, epoch ms. */
  retryAt: number;
  /** Длина текущего окна (для полосы прогресса). */
  durationMs: number;
  correlationId: string | null;
}

type Listener = () => void;

let current: RateLimitInfo | null = null;
const listeners = new Set<Listener>();
const emit = () => {
  for (const l of [...listeners]) l();
};

export const rateLimitStore = {
  getSnapshot: (): RateLimitInfo | null => current,
  getServerSnapshot: (): RateLimitInfo | null => null,

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  /** Повторный 429 во время паузы только продлевает её, никогда не укорачивает. */
  open(retryAfterSec: number, correlationId: string | null = null, now: number = Date.now()): void {
    const retryAt = Math.max(current?.retryAt ?? 0, now + retryAfterSec * 1000);
    current = { retryAt, durationMs: retryAt - now, correlationId };
    emit();
  },

  /** Сколько ещё ждать, мс (0: пауза не активна). */
  remainingMs(now: number = Date.now()): number {
    return current ? Math.max(0, current.retryAt - now) : 0;
  },

  dismiss(): void {
    if (current === null) return;
    current = null;
    emit();
  },
};
