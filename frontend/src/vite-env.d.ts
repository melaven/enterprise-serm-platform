/// <reference types="vite/client" />

/**
 * Type-safe environment variables
 * Все VITE_* переменные должны быть явно объявлены здесь
 */
interface ImportMetaEnv {
  /** 
   * Base URL для API запросов
   * @example 'http://127.0.0.1:8000' (dev)
   * @example 'https://api.tenable-serm.com' (prod)
   */
  readonly VITE_API_BASE_URL?: string;
  
  /**
   * Demo Mode флаг
   * Когда true, используются mock данные вместо реального API
   * @example 'true' | 'false'
   */
  readonly VITE_DEMO_MODE?: string;
  
  /**
   * Vite mode: 'development' | 'production'
   */
  readonly MODE: string;
  
  /**
   * Base public path
   */
  readonly BASE_URL: string;
  
  /**
   * Is production build
   */
  readonly PROD: boolean;
  
  /**
   * Is development build
   */
  readonly DEV: boolean;
  
  /**
   * Is running in SSR
   */
  readonly SSR: boolean;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
