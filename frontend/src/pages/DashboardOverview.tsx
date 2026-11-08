import { useState } from 'react';
import { Download } from 'lucide-react';
import { toast } from 'sonner';

import * as api from '@/api/services';
import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { useAppStore } from '@/store/useAppStore';
import { useDashboardSummary } from '@/hooks/api/useReviews';

/**
 * DashboardOverview — Premium B2B Analytics Dashboard
 * 
 * Features:
 * - KPI metrics cards with trends
 * - Sentiment distribution chart (Tailwind placeholder)
 * - SI activity feed
 * 
 * Design System: Strict enterprise minimalism with slate palette
 */

interface KPICardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  description?: string;
}

function KPICard({ label, value, icon, trend, description }: KPICardProps) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
            {label}
          </p>
          <p className="text-3xl font-semibold text-slate-900 tabular-nums">
            {value}
          </p>
        </div>
        <div className="text-slate-400">
          {icon}
        </div>
      </div>
      
      {trend && (
        <div className="flex items-center gap-2">
          <span
            className={`text-sm font-medium ${
              trend.isPositive ? 'text-emerald-600' : 'text-rose-600'
            }`}
          >
            {trend.isPositive ? '↑' : '↓'} {trend.value}
          </span>
          <span className="text-xs text-slate-500">vs. прошлый период</span>
        </div>
      )}
      
      {description && !trend && (
        <p className="text-xs text-slate-500 mt-2">{description}</p>
      )}
    </div>
  );
}

function SentimentChart({ dashboard }: { dashboard: api.DashboardSummary }) {
  const total = dashboard.sentiment.total || 1;
  const positivePercent = Math.round((dashboard.sentiment.positive / total) * 100);
  const neutralPercent = Math.round((dashboard.sentiment.neutral / total) * 100);
  const negativePercent = Math.round((dashboard.sentiment.negative / total) * 100);

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-1">
          Динамика тональности
        </h2>
        <p className="text-sm text-slate-500">
          Распределение отзывов по эмоциональной окраске
        </p>
      </div>

      <div className="space-y-4">
        {/* Positive Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">Позитивные</span>
            <span className="text-sm font-semibold text-emerald-600 tabular-nums">
              {positivePercent}%
            </span>
          </div>
          <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-500"
              style={{ width: `${positivePercent}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {dashboard.sentiment.positive.toLocaleString('ru-RU')} отзывов
          </p>
        </div>

        {/* Neutral Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">Нейтральные</span>
            <span className="text-sm font-semibold text-slate-600 tabular-nums">
              {neutralPercent}%
            </span>
          </div>
          <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-slate-400 rounded-full transition-all duration-500"
              style={{ width: `${neutralPercent}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {dashboard.sentiment.neutral.toLocaleString('ru-RU')} отзывов
          </p>
        </div>

        {/* Negative Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">Негативные</span>
            <span className="text-sm font-semibold text-rose-600 tabular-nums">
              {negativePercent}%
            </span>
          </div>
          <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-rose-500 rounded-full transition-all duration-500"
              style={{ width: `${negativePercent}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">
            {dashboard.sentiment.negative.toLocaleString('ru-RU')} отзывов
          </p>
        </div>
      </div>
    </div>
  );
}

interface ActivityItem {
  id: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  timestamp: string;
}

function ActivityFeed() {
  // Mock activity data — replace with real API when available
  const activities: ActivityItem[] = [
    {
      id: '1',
      icon: (
        <svg className="w-5 h-5 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ),
      title: 'SI сгенерировал ответ',
      description: 'Отзыв на 2GIS получил автоматический ответ',
      timestamp: '2 минуты назад',
    },
    {
      id: '2',
      icon: (
        <svg className="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
      title: 'Менеджер утвердил ответ',
      description: 'Ответ на отзыв Google Maps опубликован',
      timestamp: '15 минут назад',
    },
    {
      id: '3',
      icon: (
        <svg className="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
      ),
      title: 'SI обработал новый отзыв',
      description: 'Отзыв Яндекс.Карты прошел анализ тональности',
      timestamp: '1 час назад',
    },
    {
      id: '4',
      icon: (
        <svg className="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
      title: 'Обнаружен критический отзыв',
      description: '2GIS: низкий рейтинг требует внимания',
      timestamp: '3 часа назад',
    },
  ];

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-1">
          Последние действия SI
        </h2>
        <p className="text-sm text-slate-500">
          Автоматизированная обработка отзывов
        </p>
      </div>

      <div className="space-y-4">
        {activities.map((activity) => (
          <div key={activity.id} className="flex gap-3 pb-4 last:pb-0 border-b last:border-b-0 border-slate-100">
            <div className="flex-shrink-0 mt-0.5">
              {activity.icon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-slate-900">
                {activity.title}
              </p>
              <p className="text-sm text-slate-600 mt-0.5">
                {activity.description}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {activity.timestamp}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {/* KPI Cards Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
            <div className="animate-pulse space-y-4">
              <div className="flex items-start justify-between">
                <div className="space-y-2 flex-1">
                  <div className="h-3 w-24 bg-slate-200 rounded" />
                  <div className="h-8 w-20 bg-slate-200 rounded" />
                </div>
                <div className="h-6 w-6 bg-slate-200 rounded" />
              </div>
              <div className="h-3 w-32 bg-slate-200 rounded" />
            </div>
          </div>
        ))}
      </div>

      {/* Chart Skeleton */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        <div className="animate-pulse space-y-4">
          <div className="h-5 w-48 bg-slate-200 rounded" />
          <div className="space-y-3">
            <div className="h-3 w-full bg-slate-200 rounded" />
            <div className="h-3 w-5/6 bg-slate-200 rounded" />
            <div className="h-3 w-4/6 bg-slate-200 rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardOverview() {
  const { user, logout } = useAppStore();
  const dashboardQuery = useDashboardSummary();
  const dashboard = dashboardQuery.data;
  const [isExporting, setIsExporting] = useState(false);

  const handleExportCSV = async () => {
    setIsExporting(true);
    try {
      const blob = await api.exportAnalyticsToCSV({ days: 30 });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('CSV файл успешно скачан');
    } catch (error) {
      toast.error('Не удалось экспортировать данные', {
        description: error instanceof Error ? error.message : 'Попробуйте снова',
      });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <DashboardLayout
      title="Главная"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="min-h-full bg-slate-50 p-6 space-y-6">
        {/* Header */}
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Главная панель
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              Обзор ключевых метрик и активности системы
            </p>
          </div>
          <button
            onClick={handleExportCSV}
            disabled={isExporting}
            className="
              inline-flex items-center gap-2
              px-4 py-2.5
              bg-white
              border border-slate-300
              rounded-lg
              text-sm font-medium text-slate-700
              hover:bg-slate-50 hover:border-slate-400
              active:bg-slate-100
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors
              shadow-sm
            "
          >
            <Download className="w-4 h-4" />
            {isExporting ? 'Экспорт...' : 'Экспорт в CSV'}
          </button>
        </header>

        {/* Content */}
        {dashboardQuery.isLoading ? (
          <LoadingSkeleton />
        ) : dashboard ? (
          <>
            {/* KPI Metrics Grid */}
            <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <KPICard
                label="Обработано отзывов"
                value={dashboard.total_reviews.toLocaleString('ru-RU')}
                icon={
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                }
                trend={{
                  value: '+12%',
                  isPositive: true,
                }}
              />

              <KPICard
                label="Средний рейтинг"
                value="4.8"
                icon={
                  <svg className="w-6 h-6 text-amber-400" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                }
                description="Высокий уровень удовлетворенности"
              />

              <KPICard
                label="Доля SI-ответов"
                value="94%"
                icon={
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                }
                trend={{
                  value: '+8%',
                  isPositive: true,
                }}
              />

              <KPICard
                label="Среднее время ответа"
                value="1м 15с"
                icon={
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                }
                trend={{
                  value: '-45%',
                  isPositive: true,
                }}
              />
            </section>

            {/* Sentiment Chart & Activity Feed */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <SentimentChart dashboard={dashboard} />
              </div>
              <div className="lg:col-span-1">
                <ActivityFeed />
              </div>
            </div>
          </>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
            <svg
              className="w-16 h-16 text-slate-300 mx-auto mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
            <h3 className="text-lg font-semibold text-slate-900 mb-2">
              Данные недоступны
            </h3>
            <p className="text-sm text-slate-500">
              Подождите, пока система загрузит аналитику
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
