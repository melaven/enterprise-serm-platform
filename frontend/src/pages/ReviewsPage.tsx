import { useState } from 'react';
import { toast } from 'sonner';
import { Sparkles } from 'lucide-react';

import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { ReviewsTable } from '@/features/reviews/ReviewsTable';
import { ReviewFilters } from '@/features/reviews/ReviewFilters';
import { ParserStatusIndicator } from '@/features/parser/ParserStatusIndicator';
import { useParserPolling } from '@/features/parser/useParserPolling';
import { Button } from '@/components/ui/button';
import { useAppStore, useParser, useReviews } from '@/store/useAppStore';
import { Review } from '@/api/services';

const DEFAULT_PARSER_URL = 'https://2gis.ru/moscow/firm/70000001012345678/tab/reviews';

// CSV Export Utility
const exportToCSV = (reviews: Review[], filename: string = 'reviews.csv') => {
  if (reviews.length === 0) {
    toast.error('Нет данных для экспорта');
    return;
  }

  // Define CSV headers
  const headers = ['Platform', 'Author', 'Rating', 'Text', 'Sentiment', 'Date', 'Status', 'Is Critical'];
  
  // Convert reviews to CSV format
  const csvRows = [
    headers.join(','),
    ...reviews.map(review => {
      const row = [
        review.platform,
        review.author_name || 'Anonymous',
        review.rating,
        `"${review.text.replace(/"/g, '""')}"`, // Escape quotes
        review.sentiment || 'Unclassified',
        review.created_at,
        review.status,
        review.is_critical ? 'Yes' : 'No'
      ];
      return row.join(',');
    })
  ];

  // Create blob and download
  const csvContent = csvRows.join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  toast.success('CSV файл успешно скачан');
};

export function ReviewsPage() {
  const { user, logout } = useAppStore();
  const { startParser } = useParser();
  const { reviews, fetchReviews } = useReviews();
  const [url, setUrl] = useState(DEFAULT_PARSER_URL);
  const [isStarting, setIsStarting] = useState(false);

  // Состояние фильтров
  const [searchQuery, setSearchQuery] = useState('');
  const [sentimentFilter, setSentimentFilter] = useState('all');
  const [platformFilter, setPlatformFilter] = useState('all');

  // Поллинг статуса парсера с автоматическим обновлением таблицы при успехе
  const { isPolling, jobId, status } = useParserPolling({
    onSuccess: () => {
      // При успешном парсинге обновляем таблицу отзывов
      fetchReviews({ page_size: 50 });
    },
  });

  const handleStartParser = async () => {
    if (!url.trim()) {
      toast.error('Введите URL страницы');
      return;
    }

    setIsStarting(true);
    try {
      const newJobId = await startParser('2gis', url);
      if (newJobId) {
        toast.success('Сбор данных запущен', {
          description: `Задача добавлена в очередь`,
        });
      }
    } catch (error) {
      toast.error('Ошибка запуска', {
        description: error instanceof Error ? error.message : 'Не удалось запустить парсер',
      });
    } finally {
      setIsStarting(false);
    }
  };

  const handleResetFilters = () => {
    setSearchQuery('');
    setSentimentFilter('all');
    setPlatformFilter('all');
  };

  const handleExportCSV = () => {
    // Filter reviews based on current filters
    const filteredReviews = reviews.filter(review => {
      const matchesSearch = searchQuery
        ? review.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
          review.author_name?.toLowerCase().includes(searchQuery.toLowerCase())
        : true;
      const matchesSentiment = sentimentFilter === 'all' || review.sentiment === sentimentFilter;
      const matchesPlatform = platformFilter === 'all' || review.platform === platformFilter;
      return matchesSearch && matchesSentiment && matchesPlatform;
    });
    
    const timestamp = new Date().toISOString().slice(0, 10);
    exportToCSV(filteredReviews, `reviews_${timestamp}.csv`);
  };

  return (
    <DashboardLayout
      title="Отзывы"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="space-y-6">
        {/* Панель парсера */}
        <section className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="flex items-center gap-2 text-xl font-semibold text-white">
                <Sparkles className="h-5 w-5 text-plum" aria-hidden="true" />
                Сбор данных
              </h2>
              <p className="mt-1 text-sm text-chrome-400">
                Запустите парсинг отзывов с 2GIS. При исчерпанной квоте API вернёт 402.
              </p>
            </div>
            {status && jobId && (
              <ParserStatusIndicator state={status} jobId={jobId} />
            )}
          </div>

          <div className="space-y-2">
            <label htmlFor="parser-url" className="block text-sm font-medium text-chrome-300">
              Ссылка на страницу 2GIS
            </label>
            <input
              id="parser-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://2gis.ru/moscow/firm/..."
              disabled={isStarting || isPolling}
              className="w-full rounded-sm border-2 border-chrome-600 bg-ink-950 px-4 py-2.5 text-white placeholder:text-chrome-500 transition-colors focus:border-plum focus:outline-none disabled:opacity-50"
            />
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={handleStartParser}
              disabled={isStarting || isPolling || !url.trim()}
              variant="default"
              size="lg"
            >
              {isStarting ? 'Запускаем…' : 'Запустить сбор данных'}
            </Button>

            {isPolling && (
              <p className="text-sm text-chrome-400">
                Парсер работает, статус обновляется автоматически каждые 2.5 секунды
              </p>
            )}
          </div>
        </section>

        {/* Панель фильтрации */}
        <ReviewFilters
          search={searchQuery}
          sentiment={sentimentFilter}
          platform={platformFilter}
          onSearchChange={setSearchQuery}
          onSentimentChange={setSentimentFilter}
          onPlatformChange={setPlatformFilter}
          onReset={handleResetFilters}
        />

        {/* Таблица отзывов */}
        <ReviewsTable
          searchQuery={searchQuery}
          sentimentFilter={sentimentFilter}
          platformFilter={platformFilter}
          onExportCSV={handleExportCSV}
        />
      </div>
    </DashboardLayout>
  );
}
