import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { ApiError, QuotaExceededApiError } from './api/client.ts';
import { isAbortError, waitForJob, type ParserApi, type ParseResult, type Platform } from './api/parser.ts';

export type ParsingPhase = 'idle' | 'starting' | 'running';

/**
 * Запуск сбора + ожидание результата. Запросы идут через общий клиент с интерцептором,
 * поэтому 402 сам открывает модалку: здесь он молча игнорируется (без дублирующего тоста).
 */
export function useParsingJob(
  parser: ParserApi,
  onFinished?: (result: ParseResult) => void,
): { phase: ParsingPhase; isParsing: boolean; start: (platform: Platform, url: string) => Promise<void> } {
  const [phase, setPhase] = useState<ParsingPhase>('idle');
  const abortRef = useRef<AbortController | null>(null);
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;

  useEffect(() => () => abortRef.current?.abort(), []);

  const start = useCallback(
    async (platform: Platform, url: string) => {
      if (abortRef.current) return; // уже идёт
      const controller = new AbortController();
      abortRef.current = controller;
      setPhase('starting');
      try {
        const jobId = await parser.start(platform, url);
        setPhase('running');
        const final = await waitForJob(parser, jobId, { signal: controller.signal });
        if (final.state === 'succeeded' && final.result) {
          const r = final.result;
          toast.success(
            r.reviews_saved > 0 ? `Собрано новых отзывов: ${r.reviews_saved}` : 'Новых отзывов нет',
            r.ai_pending > 0
              ? { description: `Без AI-разметки: ${r.ai_pending}, будет дообработано автоматически` }
              : undefined,
          );
          finishedRef.current?.(r);
        } else {
          toast.error('Сбор завершился с ошибкой');
        }
      } catch (error) {
        if (isAbortError(error)) return; // размонтирование страницы: тихо выходим
        if (error instanceof QuotaExceededApiError) return; // модалка уже показана
        if (error instanceof ApiError && error.status === 409) {
          toast.error('Сбор по этой ссылке уже идёт');
        } else if (error instanceof ApiError && error.status === 422) {
          toast.error('Проверьте площадку и ссылку');
        } else {
          toast.error(error instanceof Error ? error.message : 'Не удалось запустить сбор');
        }
      } finally {
        abortRef.current = null;
        setPhase('idle');
      }
    },
    [parser],
  );

  return { phase, isParsing: phase !== 'idle', start };
}
