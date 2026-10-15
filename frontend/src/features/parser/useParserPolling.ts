import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { useParser } from '@/store/useAppStore';
import type { ParserJobResult } from '@/api/services';

/**
 * useParserPolling — хук для автоматического опроса статуса парсера
 * 
 * Логика:
 * 1. Когда jobId и status = queued/in_progress, начинаем поллинг каждые 2.5 секунд
 * 2. При достижении succeeded/failed останавливаем поллинг
 * 3. При succeeded показываем toast с детальными результатами и вызываем onSuccess
 * 4. При failed показываем toast с текстом ошибки
 * 
 * @param onSuccess - callback при успешном завершении парсинга
 */

interface UseParserPollingOptions {
  onSuccess?: (result: ParserJobResult | null) => void;
  pollInterval?: number; // миллисекунды (default: 2500)
}

export function useParserPolling({ onSuccess, pollInterval = 2500 }: UseParserPollingOptions = {}) {
  const { parserJobId, parserStatus, parserResult, parserError, pollParserStatus } = useParser();
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastStatusRef = useRef<typeof parserStatus>(null);

  // Очистка интервала
  const stopPolling = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  };

  // Обработка изменения статуса
  useEffect(() => {
    // Пропускаем первый рендер
    if (lastStatusRef.current === null) {
      lastStatusRef.current = parserStatus;
      return;
    }

    // Статус изменился
    if (parserStatus !== lastStatusRef.current) {
      lastStatusRef.current = parserStatus;

      if (parserStatus === 'succeeded') {
        stopPolling();
        
        // Показываем детальные результаты
        if (parserResult) {
          const duration = (parserResult.duration_ms / 1000).toFixed(1);
          toast.success('Парсинг завершен', {
            description: `Сохранено: ${parserResult.reviews_saved} отзывов, AI-анализ: ${parserResult.ai_enriched}, Время: ${duration}с`,
            duration: 5000,
          });
        } else {
          toast.success('Парсинг завершен', {
            description: 'Данные успешно загружены и обработаны',
          });
        }
        
        onSuccess?.(parserResult);
      } else if (parserStatus === 'failed') {
        stopPolling();
        toast.error('Ошибка парсинга', {
          description: parserError || 'Не удалось загрузить данные. Проверьте URL и попробуйте снова',
          duration: 6000,
        });
      }
    }
  }, [parserStatus, parserResult, parserError, onSuccess]);

  // Управление поллингом
  useEffect(() => {
    // Нет jobId или статус финальный — не запускаем поллинг
    if (!parserJobId || parserStatus === 'succeeded' || parserStatus === 'failed') {
      stopPolling();
      return;
    }

    // Статус активный (queued/in_progress) — запускаем поллинг
    if (parserStatus === 'queued' || parserStatus === 'in_progress') {
      setIsPolling(true);
      
      intervalRef.current = setInterval(async () => {
        try {
          await pollParserStatus(parserJobId);
        } catch (error) {
          console.error('[ParserPolling] Ошибка опроса статуса:', error);
          // Не останавливаем поллинг при ошибке сети, продолжаем попытки
        }
      }, pollInterval);

      // Cleanup при unmount
      return () => stopPolling();
    }

    return undefined;
  }, [parserJobId, parserStatus, pollInterval, pollParserStatus]);

  return {
    isPolling,
    jobId: parserJobId,
    status: parserStatus,
    result: parserResult,
    error: parserError,
    stopPolling,
  };
}
