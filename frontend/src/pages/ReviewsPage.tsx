import { useState } from 'react';
import { toast } from 'sonner';

import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { ReviewsTable } from '@/features/reviews/ReviewsTable';
import { ReviewFilters } from '@/features/reviews/ReviewFilters';
import { useAppStore, useReviews } from '@/store/useAppStore';
import { Review } from '@/api/services';

// CSV Export Utility
const exportToCSV = (reviews: Review[], filename: string = 'reviews.csv') => {
  if (reviews.length === 0) {
    toast.error('Нет данных для экспорта');
    return;
  }

  // Define CSV headers
  const headers = ['Platform', 'Rating', 'Sentiment', 'Threat level', 'SI tags', 'Date', 'Is Critical'];
  
  // Convert reviews to CSV format
  const csvRows = [
    headers.join(','),
    ...reviews.map(review => {
      const row = [
        review.platform,
        review.rating,
        review.sentiment || 'Unclassified',
        review.threat_level ?? '',
        `"${(review.tags ?? []).join(', ')}"`,
        review.created_at,
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
  const { reviews } = useReviews();

  // Состояние фильтров
  const [searchQuery, setSearchQuery] = useState('');
  const [sentimentFilter, setSentimentFilter] = useState('all');
  const [platformFilter, setPlatformFilter] = useState('all');

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
          review.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()))
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
        <section className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-6">
          <h2 className="text-xl font-semibold text-white">Источники данных</h2>
          <p className="mt-2 max-w-3xl text-sm text-chrome-400">
            Аналитика строится только по данным, предоставленным клиентом, или через
            официальные интеграции. Сбор отзывов с публичных страниц отключён; исходный
            текст анализируется локально и не сохраняется.
          </p>
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
