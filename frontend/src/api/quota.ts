/**
 * Глобальное состояние «квота исчерпана / подписка неактивна» (HTTP 402).
 * Без зависимостей от React/axios: подписка через useSyncExternalStore, тесты в Node.
 */

export interface QuotaExceededInfo {
  /** 'quota_exceeded' | 'subscription_inactive' | ... (бэкенд может добавить новые) */
  code: string;
  message: string;
  requestsUsed?: number;
  maxRequests?: number;
  /** Дата сброса счётчиков, ISO (если бэкенд её прислал). */
  resetDate?: string;
  correlationId?: string | null;
}

const DEFAULT_MESSAGE =
  'Лимит вашего тарифа исчерпан. Смените тариф, чтобы продолжить работу.';

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

const str = (v: unknown): string | undefined => (typeof v === 'string' && v !== '' ? v : undefined);
const num = (v: unknown): number | undefined =>
  typeof v === 'number' && Number.isFinite(v) ? v : undefined;

/**
 * Разбирает тело 402. FastAPI кладёт его в `detail`. Поддержаны оба формата бэкенда:
 *   {code, message, requests_used, max_requests}            (check_quota)
 *   {error:'quota_exceeded', used, limit, reset_date, ...}   (QuotaService)
 * Нераспознанное тело (строка, пустое) всё равно даёт валидный info: 402 без модалки
 * хуже, чем модалка с общим текстом.
 */
export function parseQuotaExceeded(data: unknown): QuotaExceededInfo {
  const detail = isRecord(data) && 'detail' in data ? data['detail'] : data;
  if (typeof detail === 'string' && detail !== '') {
    return { code: 'quota_exceeded', message: detail };
  }
  if (!isRecord(detail)) return { code: 'quota_exceeded', message: DEFAULT_MESSAGE };

  return {
    code: str(detail['code']) ?? str(detail['error']) ?? 'quota_exceeded',
    message: str(detail['message']) ?? DEFAULT_MESSAGE,
    requestsUsed: num(detail['requests_used']) ?? num(detail['used']),
    maxRequests: num(detail['max_requests']) ?? num(detail['limit']),
    resetDate: str(detail['reset_date']),
  };
}

type Listener = () => void;

let current: QuotaExceededInfo | null = null;
const listeners = new Set<Listener>();

function emit(): void {
  for (const listener of [...listeners]) listener();
}

export const quotaStore = {
  getSnapshot: (): QuotaExceededInfo | null => current,
  getServerSnapshot: (): QuotaExceededInfo | null => null,

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  /** Параллельные запросы дают пачку 402: пока модалка открыта, повторные не перезаписывают её. */
  open(info: QuotaExceededInfo): void {
    if (current !== null) return;
    current = info;
    emit();
  },

  dismiss(): void {
    if (current === null) return;
    current = null;
    emit();
  },
};
