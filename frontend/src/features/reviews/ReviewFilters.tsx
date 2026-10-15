import { Filter, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';

export interface ReviewFiltersProps {
  search: string;
  sentiment: string;
  platform: string;
  onSearchChange: (value: string) => void;
  onSentimentChange: (value: string) => void;
  onPlatformChange: (value: string) => void;
  onReset: () => void;
}

const SENTIMENT_OPTIONS = [
  { value: 'all', label: 'Все тональности' },
  { value: 'POSITIVE', label: 'Позитивные' },
  { value: 'NEUTRAL', label: 'Нейтральные' },
  { value: 'NEGATIVE', label: 'Негативные' },
  { value: 'UNCLASSIFIED', label: 'Не классифицированные' },
];

const PLATFORM_OPTIONS = [
  { value: 'all', label: 'Все платформы' },
  { value: '2gis', label: '2GIS' },
];

/**
 * Панель фильтрации отзывов
 * B2B минимализм: border-2, rounded-sm, Royal Plum icons
 */
export function ReviewFilters({
  search,
  sentiment,
  platform,
  onSearchChange,
  onSentimentChange,
  onPlatformChange,
  onReset,
}: ReviewFiltersProps) {
  const hasActiveFilters = search || sentiment !== 'all' || platform !== 'all';

  return (
    <div className="rounded-sm border-2 border-chrome-600 bg-ink-900 p-6">
      <div className="mb-4 flex items-center gap-2">
        <Filter className="h-5 w-5 text-plum" aria-hidden="true" />
        <h3 className="text-lg font-semibold text-white">Фильтры</h3>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={onReset} className="ml-auto">
            Сбросить
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Поиск */}
        <div className="space-y-2">
          <label htmlFor="search" className="block text-sm font-medium text-chrome-300">
            Поиск по тексту
          </label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-chrome-500 pointer-events-none" aria-hidden="true" />
            <Input
              id="search"
              type="text"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Искать в отзывах..."
              className="pl-10"
              aria-label="Поиск по тексту отзыва"
            />
          </div>
        </div>

        {/* Тональность */}
        <div className="space-y-2">
          <label htmlFor="sentiment" className="block text-sm font-medium text-chrome-300">
            Тональность
          </label>
          <Select
            id="sentiment"
            value={sentiment}
            onChange={(e) => onSentimentChange(e.target.value)}
            options={SENTIMENT_OPTIONS}
            aria-label="Фильтр по тональности"
          />
        </div>

        {/* Платформа */}
        <div className="space-y-2">
          <label htmlFor="platform" className="block text-sm font-medium text-chrome-300">
            Платформа
          </label>
          <Select
            id="platform"
            value={platform}
            onChange={(e) => onPlatformChange(e.target.value)}
            options={PLATFORM_OPTIONS}
            aria-label="Фильтр по платформе"
          />
        </div>
      </div>
    </div>
  );
}
