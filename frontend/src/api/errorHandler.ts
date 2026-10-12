import { toast } from 'sonner';
import axios, { AxiosError } from 'axios';

/**
 * Централизованная обработка ошибок API
 * Обрабатывает стандартные HTTP коды и показывает соответствующие уведомления
 */

export interface ApiError {
  statusCode: number;
  message: string;
  detail?: string;
}

/**
 * Извлекает сообщение об ошибке из ответа API
 */
function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string; message?: string }>;
    return axiosError.response?.data?.detail 
      || axiosError.response?.data?.message 
      || axiosError.message 
      || 'Неизвестная ошибка';
  }
  
  if (error instanceof Error) {
    return error.message;
  }
  
  return 'Неизвестная ошибка';
}

/**
 * Обрабатывает ошибку API и показывает toast уведомление
 * @param error - ошибка от axios или другого источника
 * @param customHandlers - кастомные обработчики для определённых статус-кодов
 * @returns объект ApiError с деталями
 */
export function handleApiError(
  error: unknown,
  customHandlers?: Record<number, (error: ApiError) => void>
): ApiError {
  const message = extractErrorMessage(error);
  let statusCode = 500;

  if (axios.isAxiosError(error) && error.response) {
    statusCode = error.response.status;
  }

  const apiError: ApiError = {
    statusCode,
    message,
    detail: axios.isAxiosError(error) ? error.response?.data?.detail : undefined,
  };

  // Проверяем кастомные обработчики
  if (customHandlers && customHandlers[statusCode]) {
    customHandlers[statusCode](apiError);
    return apiError;
  }

  // Стандартная обработка по статус-кодам
  switch (statusCode) {
    case 401:
      // Уже обработано в axios interceptor (redirect на /login)
      toast.error('Сессия истекла. Пожалуйста, войдите снова.');
      break;

    case 402:
      toast.error('Превышен лимит квоты', {
        description: 'Пожалуйста, обновите тарифный план для продолжения работы',
        duration: 5000,
      });
      break;

    case 403:
      toast.error('Доступ запрещён', {
        description: message,
      });
      break;

    case 404:
      toast.error('Ресурс не найден', {
        description: message,
      });
      break;

    case 422:
      toast.error('Ошибка валидации', {
        description: message,
      });
      break;

    case 429:
      toast.error('Слишком много запросов', {
        description: 'Пожалуйста, попробуйте позже',
        duration: 4000,
      });
      break;

    case 500:
    case 502:
    case 503:
      toast.error('Ошибка сервера', {
        description: 'Попробуйте повторить запрос позже',
      });
      break;

    default:
      toast.error('Произошла ошибка', {
        description: message,
      });
  }

  return apiError;
}

/**
 * Оборачивает async функцию с автоматической обработкой ошибок
 * @param fn - async функция для выполнения
 * @param customHandlers - кастомные обработчики ошибок
 * @returns результат функции или undefined при ошибке
 */
export async function withErrorHandling<T>(
  fn: () => Promise<T>,
  customHandlers?: Record<number, (error: ApiError) => void>
): Promise<T | undefined> {
  try {
    return await fn();
  } catch (error) {
    handleApiError(error, customHandlers);
    return undefined;
  }
}
