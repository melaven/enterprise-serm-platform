import { useState } from 'react';

/**
 * ReviewsFilterBar — Premium B2B filter panel for reviews
 * 
 * Features:
 * - Search by review text
 * - Filter by reply status (pending, draft, published)
 * - Filter by sentiment (positive, neutral, negative)
 * - Filter by platform (Яндекс.Карты, 2GIS, Google Maps)
 * - Results counter
 * 
 * Design System: Enterprise minimalism with slate palette
 */

export interface ReviewsFilters {
  search: string;
  replyStatus: 'all' | 'pending' | 'draft' | 'published';
  sentiment: 'all' | 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  platform: 'all' | 'yandex' | '2gis' | 'google';
}

interface ReviewsFilterBarProps {
  filters: ReviewsFilters;
  onFiltersChange: (filters: ReviewsFilters) => void;
  totalCount: number;
}

export function ReviewsFilterBar({ filters, onFiltersChange, totalCount }: ReviewsFilterBarProps) {
  const [searchInput, setSearchInput] = useState(filters.search);

  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    // Debounce: update filters after user stops typing
    const timeoutId = setTimeout(() => {
      onFiltersChange({ ...filters, search: value });
    }, 300);
    return () => clearTimeout(timeoutId);
  };

  const replyStatusOptions = [
    { value: 'all' as const, label: 'Все' },
    { value: 'pending' as const, label: 'Ожидают SI' },
    { value: 'draft' as const, label: 'Черновики' },
    { value: 'published' as const, label: 'Опубликованы' },
  ];

  const sentimentOptions = [
    { value: 'all' as const, label: 'Все' },
    { value: 'NEGATIVE' as const, label: 'Негативные' },
    { value: 'NEUTRAL' as const, label: 'Нейтральные' },
    { value: 'POSITIVE' as const, label: 'Позитивные' },
  ];

  const platformOptions = [
    { value: 'all' as const, label: 'Все источники' },
    { value: 'yandex' as const, label: 'Яндекс.Карты' },
    { value: '2gis' as const, label: '2GIS' },
    { value: 'google' as const, label: 'Google Maps' },
  ];

  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm space-y-4">
      {/* Search Input */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <svg
            className="h-4 w-4 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
        </div>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder="Поиск по тексту отзыва..."
          className="
            w-full
            pl-10
            pr-4
            py-2.5
            text-sm
            text-slate-800
            placeholder:text-slate-400
            bg-white
            border
            border-slate-200
            rounded-md
            focus:ring-2
            focus:ring-slate-500
            focus:border-slate-500
            focus:outline-none
            transition-colors
          "
        />
      </div>

      {/* Filters Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        
        {/* Reply Status Filter */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">
            Статус ответа
          </label>
          <div className="flex gap-1 flex-wrap">
            {replyStatusOptions.map((option) => (
              <button
                key={option.value}
                onClick={() =>
                  onFiltersChange({ ...filters, replyStatus: option.value })
                }
                className={`
                  px-3
                  py-1.5
                  text-xs
                  font-medium
                  rounded-md
                  transition-colors
                  ${
                    filters.replyStatus === option.value
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200'
                  }
                `}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sentiment Filter */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">
            Тональность
          </label>
          <div className="flex gap-1 flex-wrap">
            {sentimentOptions.map((option) => (
              <button
                key={option.value}
                onClick={() =>
                  onFiltersChange({ ...filters, sentiment: option.value })
                }
                className={`
                  px-3
                  py-1.5
                  text-xs
                  font-medium
                  rounded-md
                  transition-colors
                  ${
                    filters.sentiment === option.value
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200'
                  }
                `}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Platform Filter */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1.5">
            Площадка
          </label>
          <select
            value={filters.platform}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                platform: e.target.value as ReviewsFilters['platform'],
              })
            }
            className="
              w-full
              px-3
              py-2
              text-sm
              text-slate-800
              bg-white
              border
              border-slate-200
              rounded-md
              focus:ring-2
              focus:ring-slate-500
              focus:border-slate-500
              focus:outline-none
              transition-colors
            "
          >
            {platformOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {/* Results Counter */}
        <div className="flex items-end">
          <div className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-md">
            <p className="text-xs text-slate-500 mb-0.5">Показано:</p>
            <p className="text-lg font-semibold text-slate-900 tabular-nums">
              {totalCount}
            </p>
          </div>
        </div>
      </div>

      {/* Active Filters Summary */}
      {(filters.search ||
        filters.replyStatus !== 'all' ||
        filters.sentiment !== 'all' ||
        filters.platform !== 'all') && (
        <div className="flex items-center gap-2 pt-2 border-t border-slate-100">
          <span className="text-xs text-slate-500">Активные фильтры:</span>
          <div className="flex gap-2 flex-wrap">
            {filters.search && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 text-slate-700 text-xs rounded-md">
                Поиск: "{filters.search}"
                <button
                  onClick={() => {
                    setSearchInput('');
                    onFiltersChange({ ...filters, search: '' });
                  }}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </span>
            )}
            {filters.replyStatus !== 'all' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 text-slate-700 text-xs rounded-md">
                Статус: {replyStatusOptions.find((o) => o.value === filters.replyStatus)?.label}
                <button
                  onClick={() => onFiltersChange({ ...filters, replyStatus: 'all' })}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </span>
            )}
            {filters.sentiment !== 'all' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 text-slate-700 text-xs rounded-md">
                Тональность: {sentimentOptions.find((o) => o.value === filters.sentiment)?.label}
                <button
                  onClick={() => onFiltersChange({ ...filters, sentiment: 'all' })}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </span>
            )}
            {filters.platform !== 'all' && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-100 text-slate-700 text-xs rounded-md">
                Площадка: {platformOptions.find((o) => o.value === filters.platform)?.label}
                <button
                  onClick={() => onFiltersChange({ ...filters, platform: 'all' })}
                  className="hover:text-slate-900"
                >
                  ×
                </button>
              </span>
            )}
            <button
              onClick={() => {
                setSearchInput('');
                onFiltersChange({
                  search: '',
                  replyStatus: 'all',
                  sentiment: 'all',
                  platform: 'all',
                });
              }}
              className="text-xs text-slate-500 hover:text-slate-700 underline"
            >
              Очистить все
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
