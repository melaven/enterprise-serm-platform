import axios, { type AxiosInstance } from 'axios';

import { ApiError } from './client.ts';

/** Отмена: axios бросает CanceledError, наш sleep — DOMException('AbortError'). */
export function isAbortError(error: unknown): boolean {
  return axios.isCancel(error) || (error instanceof DOMException && error.name === 'AbortError');
}

export type Platform = '2gis' | 'yandex' | 'google' | 'trustpilot';
export type ParseJobState = 'queued' | 'in_progress' | 'succeeded' | 'failed' | 'not_found';

export interface ParseResult {
  reviews_found: number;
  reviews_new: number;
  reviews_saved: number;
  ai_enriched: number;
  ai_pending: number;
  duration_ms: number;
}

export interface ParseJobStatus {
  job_id: string;
  state: ParseJobState;
  result: ParseResult | null;
  error: string | null;
}

export function createParserApi(client: AxiosInstance) {
  return {
    /** POST /api/v1/parser/start → job_id. 402 открывает глобальную модалку (интерцептор клиента). */
    async start(platform: Platform, url: string): Promise<string> {
      const { data } = await client.post<{ job_id: string }>('/api/v1/parser/start', { platform, url });
      return data.job_id;
    },

    async status(jobId: string, signal?: AbortSignal): Promise<ParseJobStatus> {
      const { data } = await client.get<ParseJobStatus>(
        `/api/v1/parser/jobs/${encodeURIComponent(jobId)}`,
        { signal, skipQuotaDialog: true },
      );
      return data;
    },
  };
}

export type ParserApi = ReturnType<typeof createParserApi>;

export interface WaitOptions {
  signal?: AbortSignal;
  intervalMs?: number;
  timeoutMs?: number;
  /** Подряд идущих сетевых/5xx-сбоев опроса, которые терпим. */
  maxTransientErrors?: number;
  onTick?: (status: ParseJobStatus) => void;
  sleep?: (ms: number, signal?: AbortSignal) => Promise<void>;
}

const defaultSleep = (ms: number, signal?: AbortSignal): Promise<void> =>
  new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'));
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });

/** Опрашивает задачу до succeeded/failed. Бросает при таймауте, отмене и устойчивых сбоях. */
export async function waitForJob(
  parser: ParserApi,
  jobId: string,
  options: WaitOptions = {},
): Promise<ParseJobStatus> {
  const {
    signal,
    intervalMs = 3_000,
    timeoutMs = 10 * 60_000,
    maxTransientErrors = 3,
    onTick,
    sleep = defaultSleep,
  } = options;
  const deadline = Date.now() + timeoutMs;
  let transient = 0;

  for (;;) {
    try {
      const status = await parser.status(jobId, signal);
      transient = 0;
      onTick?.(status);
      if (status.state === 'succeeded' || status.state === 'failed') return status;
    } catch (error) {
      if (error instanceof ApiError && (error.status === 0 || error.status >= 500)) {
        transient += 1;
        if (transient > maxTransientErrors) throw error;
      } else {
        throw error; // 404 (чужая/протухшая задача), 401, отмена и т.п.
      }
    }
    if (Date.now() + intervalMs > deadline) throw new Error('Превышено время ожидания задачи');
    await sleep(intervalMs, signal);
  }
}
