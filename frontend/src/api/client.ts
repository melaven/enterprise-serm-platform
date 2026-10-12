import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';

/**
 * Базовый HTTP клиент для взаимодействия с RLS-бэкендом
 * Автоматически добавляет JWT токен из localStorage во все запросы
 */

// Ключ для хранения токена в localStorage
const TOKEN_STORAGE_KEY = 'auth_token';

// Базовый URL API (можно вынести в environment variables)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function getErrorDetail(data: unknown): unknown {
  if (typeof data === 'object' && data !== null && 'detail' in data) {
    return data.detail;
  }
  return undefined;
}

/**
 * Создаем экземпляр Axios с базовой конфигурацией
 */
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 секунд
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request Interceptor
 * Извлекает JWT токен из localStorage и добавляет в заголовок Authorization
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

/**
 * Response Interceptor
 * Обрабатывает ошибки авторизации и автоматически редиректит на логин
 */
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error: AxiosError) => {
    // Если получили 401 - токен невалидный или истек
    if (error.response?.status === 401) {
      // Удаляем невалидный токен
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      
      // Редиректим на страницу логина (если не на ней)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    
    // Если получили 403 - недостаточно прав (RLS блокировка)
    if (error.response?.status === 403) {
      console.error('Access forbidden: insufficient permissions or tenant mismatch');
    }

    if (error.response?.status === 402) {
      window.dispatchEvent(
        new CustomEvent<unknown>('quota-exceeded', {
          detail: getErrorDetail(error.response.data),
        })
      );
    }
    
    return Promise.reject(error);
  }
);

/**
 * Утилиты для работы с токеном
 */
export const auth = {
  /**
   * Сохранить токен в localStorage
   */
  setToken: (token: string): void => {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  },
  
  /**
   * Получить токен из localStorage
   */
  getToken: (): string | null => {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  },
  
  /**
   * Удалить токен из localStorage
   */
  clearToken: (): void => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  },
  
  /**
   * Проверить, есть ли токен
   */
  hasToken: (): boolean => {
    return !!localStorage.getItem(TOKEN_STORAGE_KEY);
  },
};

export { apiClient };
