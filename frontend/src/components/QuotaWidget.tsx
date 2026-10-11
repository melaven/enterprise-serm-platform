import { useEffect } from 'react';
import apiClient from '../api/client';
import { useQuotas } from '../store/useAppStore';

/**
 * Виджет биллинга с прогресс-барами квот
 * Строгий flat-design, никаких теней и скруглений
 * Использует Zustand для управления состоянием
 */
export const QuotaWidget = () => {
  const { quotas, quotasLoading, quotasError, setQuotas, setQuotasLoading, setQuotasError } = useQuotas();

  useEffect(() => {
    fetchQuotas();
  }, []);

  const fetchQuotas = async () => {
    try {
      setQuotasLoading(true);
      const response = await apiClient.get('/api/v1/quotas/status');
      setQuotas(response.data);
    } catch (err: any) {
      // Если бэкенд не доступен, используем мок-данные
      console.warn('Failed to fetch quotas, using mock data:', err.message);
      setQuotas({
        llm_tokens: {
          used: 45678,
          limit: 100000,
          percentage: 45.7,
        },
        parsing_requests: {
          used: 1234,
          limit: 5000,
          percentage: 24.7,
        },
        period_start: '2026-10-01T00:00:00Z',
        period_end: '2026-10-31T23:59:59Z',
      });
      setQuotasError('Offline mode');
    }
  };

  if (quotasLoading) {
    return (
      <div className="px-4 py-3 border-t border-chrome-600">
        <div className="animate-pulse-slow">
          <div className="h-3 bg-chrome-600/30 rounded-none mb-2"></div>
          <div className="h-3 bg-chrome-600/30 rounded-none"></div>
        </div>
      </div>
    );
  }

  if (!quotas) return null;

  return (
    <div className="px-4 py-3 border-t border-chrome-600">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-medium text-chrome-400 uppercase tracking-wider">
          Квоты
        </p>
        {quotasError && (
          <span className="text-[10px] text-chrome-500">{quotasError}</span>
        )}
      </div>

      {/* LLM Tokens Quota */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-chrome-300">LLM Токены</span>
          <span className="text-xs font-medium text-chrome-300">
            {quotas.llm_tokens.used.toLocaleString()} / {quotas.llm_tokens.limit.toLocaleString()}
          </span>
        </div>
        
        {/* Progress Bar - СТРОГО без скруглений */}
        <div className="h-1 bg-chrome-600/20 rounded-none overflow-hidden">
          <div 
            className="h-full bg-[#C5FF4A] transition-all duration-300"
            style={{ width: `${Math.min(quotas.llm_tokens.percentage, 100)}%` }}
          />
        </div>
        
        <p className="text-[10px] text-chrome-500 mt-1">
          {quotas.llm_tokens.percentage.toFixed(1)}% использовано
        </p>
      </div>

      {/* Parsing Requests Quota */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-chrome-300">Парсинг</span>
          <span className="text-xs font-medium text-chrome-300">
            {quotas.parsing_requests.used.toLocaleString()} / {quotas.parsing_requests.limit.toLocaleString()}
          </span>
        </div>
        
        {/* Progress Bar - СТРОГО без скруглений */}
        <div className="h-1 bg-chrome-600/20 rounded-none overflow-hidden">
          <div 
            className="h-full bg-[#C5FF4A] transition-all duration-300"
            style={{ width: `${Math.min(quotas.parsing_requests.percentage, 100)}%` }}
          />
        </div>
        
        <p className="text-[10px] text-chrome-500 mt-1">
          {quotas.parsing_requests.percentage.toFixed(1)}% использовано
        </p>
      </div>

      {/* Warning if approaching limit */}
      {(quotas.llm_tokens.percentage > 80 || quotas.parsing_requests.percentage > 80) && (
        <div className="mt-3 px-2 py-1 bg-[#C5FF4A]/10 border border-[#C5FF4A]/30 rounded-none">
          <p className="text-[10px] text-[#C5FF4A] font-medium">
            ⚠ Приближение к лимиту
          </p>
        </div>
      )}
    </div>
  );
};
