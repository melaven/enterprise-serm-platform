import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import apiClient from '../api/client';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

/**
 * Панель аналитики с использованием shadcn/ui
 * Показывает агрегированную статистику по отзывам
 */

interface AnalyticsData {
  total_reviews: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  avg_rating: number;
  trend: 'up' | 'down' | 'stable';
  trend_percentage: number;
}

export const AnalysisPanel = () => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [parserLoading, setParserLoading] = useState(false);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/v1/analytics/summary');
      setAnalytics(response.data);
    } catch (err) {
      console.warn('Failed to fetch analytics, using mock data');
      // Мок-данные
      setAnalytics({
        total_reviews: 0,
        positive_count: 0,
        negative_count: 0,
        neutral_count: 0,
        avg_rating: 0,
        trend: 'stable',
        trend_percentage: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleStartParser = async () => {
    try {
      setParserLoading(true);
      
      await apiClient.post('/api/v1/parsers/start');
      
      toast.success('Сбор отзывов запущен!', {
        description: 'Отзывы будут обработаны в фоновом режиме',
        duration: 4000,
      });
      
      // Обновляем аналитику через 2 секунды
      setTimeout(() => {
        fetchAnalytics();
      }, 2000);
    } catch (error: any) {
      console.error('Failed to start parser:', error);
      
      // Перехватываем ошибку 402 Payment Required
      if (error.response?.status === 402) {
        toast.error('Ошибка биллинга: Лимит токенов или запросов исчерпан', {
          description: 'Пожалуйста, обновите тарифный план или дождитесь следующего периода',
          duration: 6000,
        });
      } else if (error.response?.status === 429) {
        toast.error('Слишком много запросов', {
          description: 'Попробуйте позже',
        });
      } else {
        toast.error('Не удалось запустить сбор отзывов', {
          description: error.response?.data?.detail || 'Неизвестная ошибка',
        });
      }
    } finally {
      setParserLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="card p-6">
        <div className="animate-pulse-slow space-y-4">
          <div className="h-6 bg-chrome-600/30 rounded-none w-1/3"></div>
          <div className="h-24 bg-chrome-600/30 rounded-none"></div>
        </div>
      </div>
    );
  }

  if (!analytics) return null;

  const positivePercentage = analytics.total_reviews > 0 
    ? (analytics.positive_count / analytics.total_reviews) * 100 
    : 0;
  const negativePercentage = analytics.total_reviews > 0
    ? (analytics.negative_count / analytics.total_reviews) * 100
    : 0;
  const neutralPercentage = analytics.total_reviews > 0
    ? (analytics.neutral_count / analytics.total_reviews) * 100
    : 0;

  return (
    <div className="space-y-6">
      {/* Overview Card */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold text-chrome-300">
            Аналитика отзывов
          </h3>
          <div className="flex gap-3">
            {/* Кнопка запуска сбора - ГЛАВНАЯ ЭКШН */}
            <Button 
              onClick={handleStartParser}
              disabled={parserLoading}
              className="bg-[#5A189A] hover:bg-[#7B36B3]"
            >
              {parserLoading ? 'Запуск...' : '▶ Запустить сбор'}
            </Button>
            <Button variant="outline" size="sm">
              Экспорт
            </Button>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-6 mb-6">
          {/* Total Reviews */}
          <div>
            <p className="text-label mb-2">Всего отзывов</p>
            <p className="text-3xl font-semibold text-chrome-300">
              {analytics.total_reviews.toLocaleString()}
            </p>
          </div>

          {/* Average Rating */}
          <div>
            <p className="text-label mb-2">Средний рейтинг</p>
            <p className="text-3xl font-semibold text-chrome-300 flex items-center gap-2">
              {analytics.avg_rating.toFixed(1)}
              <span className="text-[#C5FF4A] text-xl">★</span>
            </p>
          </div>

          {/* Trend */}
          <div>
            <p className="text-label mb-2">Тренд</p>
            <div className="flex items-center gap-2">
              <span className={`text-2xl ${analytics.trend === 'up' ? 'text-[#C5FF4A]' : analytics.trend === 'down' ? 'text-destructive' : 'text-chrome-400'}`}>
                {analytics.trend === 'up' ? '↑' : analytics.trend === 'down' ? '↓' : '→'}
              </span>
              <span className="text-2xl font-semibold text-chrome-300">
                {analytics.trend_percentage}%
              </span>
            </div>
          </div>

          {/* Status */}
          <div>
            <p className="text-label mb-2">Статус</p>
            <Badge variant="success" className="text-sm px-3 py-1">
              Активен
            </Badge>
          </div>
        </div>

        {/* Sentiment Distribution */}
        {analytics.total_reviews > 0 && (
          <div>
            <p className="text-label mb-3">Распределение тональности</p>
            
            {/* Sentiment Bars */}
            <div className="space-y-3">
              {/* Positive */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="success" className="text-xs">Позитивные</Badge>
                    <span className="text-sm text-chrome-400">
                      {analytics.positive_count} отзывов
                    </span>
                  </div>
                  <span className="text-sm font-medium text-chrome-300">
                    {positivePercentage.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 bg-chrome-600/20 rounded-none overflow-hidden">
                  <div 
                    className="h-full bg-[#C5FF4A] transition-all duration-300"
                    style={{ width: `${positivePercentage}%` }}
                  />
                </div>
              </div>

              {/* Neutral */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">Нейтральные</Badge>
                    <span className="text-sm text-chrome-400">
                      {analytics.neutral_count} отзывов
                    </span>
                  </div>
                  <span className="text-sm font-medium text-chrome-300">
                    {neutralPercentage.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 bg-chrome-600/20 rounded-none overflow-hidden">
                  <div 
                    className="h-full bg-chrome-500 transition-all duration-300"
                    style={{ width: `${neutralPercentage}%` }}
                  />
                </div>
              </div>

              {/* Negative */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="destructive" className="text-xs">Негативные</Badge>
                    <span className="text-sm text-chrome-400">
                      {analytics.negative_count} отзывов
                    </span>
                  </div>
                  <span className="text-sm font-medium text-chrome-300">
                    {negativePercentage.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 bg-chrome-600/20 rounded-none overflow-hidden">
                  <div 
                    className="h-full bg-destructive transition-all duration-300"
                    style={{ width: `${negativePercentage}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty State для аналитики */}
        {analytics.total_reviews === 0 && (
          <div className="flex flex-col items-center justify-center py-8 border-t border-chrome-600 mt-6">
            <p className="text-chrome-500 text-sm">
              Нет данных для отображения. Запустите сбор отзывов.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
