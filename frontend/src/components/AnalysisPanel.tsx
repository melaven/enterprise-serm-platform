import { useEffect } from 'react';
import { toast } from 'sonner';
import { useAnalytics, useParser } from '../store/useAppStore';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

/**
 * Панель аналитики
 * Использует centralized API через Zustand store
 */
export const AnalysisPanel = () => {
  const { analytics, analyticsLoading, fetchAnalytics } = useAnalytics();
  const { startParser, parserStatus } = useParser();

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const handleStartParser = async () => {
    const jobId = await startParser('https://2gis.ru/moscow/firm/70000001012345678/tab/reviews', 100);
    
    if (jobId) {
      toast.success('Сбор отзывов запущен!', {
        description: `Job ID: ${jobId}`,
        duration: 4000,
      });
      
      // Обновляем аналитику через 2 секунды
      setTimeout(() => {
        fetchAnalytics();
      }, 2000);
    }
  };

  if (analyticsLoading) {
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
    ? (analytics.sentiment_distribution.positive / analytics.total_reviews) * 100 
    : 0;
  const negativePercentage = analytics.total_reviews > 0
    ? (analytics.sentiment_distribution.negative / analytics.total_reviews) * 100
    : 0;
  const neutralPercentage = analytics.total_reviews > 0
    ? (analytics.sentiment_distribution.neutral / analytics.total_reviews) * 100
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
              disabled={parserStatus === 'running'}
              className="bg-[#5A189A] hover:bg-[#7B36B3]"
            >
              {parserStatus === 'running' ? 'Запуск...' : '▶ Запустить сбор'}
            </Button>
            <Button variant="outline" size="sm">
              Экспорт
            </Button>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-6 mb-6">
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

          {/* Top Topics */}
          <div>
            <p className="text-label mb-2">Главные темы</p>
            <div className="flex flex-wrap gap-1">
              {analytics.top_topics.slice(0, 3).map((topic, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {topic.topic} ({topic.count})
                </Badge>
              ))}
            </div>
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
                      {analytics.sentiment_distribution.positive} отзывов
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
                      {analytics.sentiment_distribution.neutral} отзывов
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
                      {analytics.sentiment_distribution.negative} отзывов
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
