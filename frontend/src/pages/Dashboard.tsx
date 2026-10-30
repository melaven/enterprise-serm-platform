import { useEffect, useState } from 'react';
import { CircleAlert, Download, MessageSquareText, MessagesSquare, Sparkles, TrendingUp, TrendingDown } from 'lucide-react';
import { toast } from 'sonner';

import * as api from '@/api/services';
import { AsyncView } from '@/components/ui/async-view';
import { Badge, type BadgeProps } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { Skeleton } from '@/components/ui/skeleton';
import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { useReviews, useDashboard, useAppStore } from '@/store/useAppStore';

type Review = api.Review;

interface DashboardMetric {
  id: string;
  label: string;
  value: string;
  detail: string;
  icon: typeof MessageSquareText;
  trend?: {
    value: number; // Процент изменения
    direction: 'up' | 'down';
  };
}

const reviewColumns: readonly DataTableColumn<Review>[] = [
  {
    key: 'platform',
    header: 'Платформа',
    cell: (review) => <span className="font-medium text-chrome-200">{review.platform || 'Не указан'}</span>,
  },
  {
    key: 'rating',
    header: 'Оценка',
    cell: (review) => <span className="font-medium tabular-nums">{review.rating} / 5</span>,
  },
  {
    key: 'moderation_status',
    header: 'Статус модерации',
    cell: (review) => {
      const statusLabels: Record<NonNullable<Review['moderation_status']>, string> = {
        new: 'Новый',
        drafted: 'Черновик',
        pending_moderation: 'На модерации',
        published: 'Опубликован',
      };
      const variant: BadgeProps['variant'] =
        review.moderation_status === 'published'
          ? 'success'
          : review.moderation_status === 'pending_moderation'
            ? 'default'
            : 'secondary';

      return (
        <Badge variant={variant}>
          {review.moderation_status ? statusLabels[review.moderation_status] : 'Не указан'}
        </Badge>
      );
    },
  },
  {
    key: 'created_at',
    header: 'Дата',
    cell: (review) => (
      <span className="whitespace-nowrap text-chrome-400">
        {new Date(review.created_at).toLocaleString('ru-RU')}
      </span>
    ),
  },
];

function DashboardLoading() {
  return (
    <div aria-label="Загрузка аналитики" className="space-y-6" role="status">
      {/* Metric Cards Skeleton */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Card className="border-2 border-chrome-600 bg-ink-900" key={index}>
            <CardHeader className="flex-row items-start justify-between space-y-0 p-5 pb-3">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-5 w-5 rounded-sm" />
            </CardHeader>
            <CardContent className="space-y-3 px-5 pb-5">
              <Skeleton className="h-8 w-20" />
              <Skeleton className="h-3 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Reviews Table Skeleton */}
      <Card className="border-2 border-chrome-600 bg-ink-900">
        <CardHeader className="border-b-2 border-chrome-600 bg-ink-950 px-6 py-4">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="mt-1 h-4 w-64" />
        </CardHeader>
        <CardContent className="space-y-3 p-6">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton className="h-12 w-full" key={index} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export default function Dashboard() {
  const { user, logout } = useAppStore();
  const { reviews, reviewsLoading, reviewsTotal, fetchReviews } = useReviews();
  const { dashboard, dashboardLoading, fetchDashboard } = useDashboard();
  const [isExporting, setIsExporting] = useState(false);

  // Load data on mount
  useEffect(() => {
    void fetchDashboard();
    void fetchReviews({ page: 1, page_size: 5 });
  }, [fetchDashboard, fetchReviews]);

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

  const metrics: DashboardMetric[] = dashboard
    ? [
        {
          id: 'reviews',
          label: 'Всего отзывов',
          value: dashboard.total_reviews.toLocaleString('ru-RU'),
          detail: `${dashboard.sentiment.total.toLocaleString('ru-RU')} учтено в тональности`,
          icon: MessagesSquare,
          trend: {
            value: 12.5,
            direction: 'up',
          },
        },
        {
          id: 'negative',
          label: 'Негативные',
          value: dashboard.sentiment.negative.toLocaleString('ru-RU'),
          detail: `${dashboard.sentiment.positive.toLocaleString('ru-RU')} положительных`,
          icon: MessageSquareText,
          trend: {
            value: 8.2,
            direction: 'down',
          },
        },
        {
          id: 'critical',
          label: 'Критические',
          value: dashboard.critical_reviews.toLocaleString('ru-RU'),
          detail: 'требуют внимания команды',
          icon: CircleAlert,
          trend: {
            value: 5.3,
            direction: 'down',
          },
        },
        {
          id: 'si-pending',
          label: 'Без SI-оценки',
          value: dashboard.ai_pending.toLocaleString('ru-RU'),
          detail: `${dashboard.sentiment.unclassified.toLocaleString('ru-RU')} без тональности`,
          icon: Sparkles,
        },
      ]
    : [];

  return (
    <DashboardLayout
      title="Обзор"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="min-h-full space-y-6 bg-ink-950">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm text-chrome-400">Сводка по репутации</p>
            <h1 className="mt-1 text-2xl font-semibold text-chrome-50">Главная</h1>
          </div>
          <div className="flex items-center gap-3">
            <p className="text-sm text-chrome-500">Последние 30 дней</p>
            <Button
              variant="outline"
              onClick={handleExportCSV}
              disabled={isExporting}
              className="border-[#5A189A] text-[#5A189A] hover:bg-[#5A189A]/10"
              style={{ borderColor: '#5A189A', color: '#5A189A' }}
            >
              <Download className="h-4 w-4 mr-2" />
              {isExporting ? 'Экспорт...' : 'Export to CSV'}
            </Button>
          </div>
        </header>

        <AsyncView
          isLoading={dashboardLoading || reviewsLoading}
          isEmpty={!dashboardLoading && !reviewsLoading && !dashboard && reviews.length === 0}
          emptyMessage="Данные пока недоступны"
          loadingComponent={<DashboardLoading />}
        >
          {dashboard && (
            <div className="space-y-6">
              <section aria-label="Ключевые показатели" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {metrics.map((metric) => {
                  const Icon = metric.icon;
                  const TrendIcon = metric.trend?.direction === 'up' ? TrendingUp : TrendingDown;

                  return (
                    <Card
                      className={metric.id === 'reviews'
                        ? 'border border-plum-700 bg-plum-900 transition-colors hover:border-plum-500'
                        : 'border border-chrome-600 bg-ink-900 transition-colors hover:border-plum-500'}
                      key={metric.id}
                    >
                      <CardHeader className="flex-row items-start justify-between space-y-0 p-5 pb-3">
                        <CardTitle className="text-sm font-medium uppercase tracking-wider text-chrome-400">
                          {metric.label}
                        </CardTitle>
                        <Icon aria-hidden="true" className="h-5 w-5 text-plum" />
                      </CardHeader>
                      <CardContent className="px-5 pb-5">
                        <div className="flex items-baseline gap-3">
                          <p className="text-3xl font-semibold tabular-nums text-white">
                            {metric.value}
                          </p>
                          {metric.trend && (
                            <Badge 
                              variant={metric.trend.direction === 'up' ? 'success' : 'secondary'}
                              className="gap-1"
                            >
                              <TrendIcon className="h-3 w-3" aria-hidden="true" />
                              <span className="tabular-nums">{metric.trend.value}%</span>
                            </Badge>
                          )}
                        </div>
                        <p className="mt-2 text-xs text-chrome-400">{metric.detail}</p>
                      </CardContent>
                    </Card>
                  );
                })}
              </section>

              <Card className="overflow-hidden border-2 border-chrome-600 bg-ink-900">
                <CardHeader className="border-b-2 border-chrome-600 bg-ink-950 px-6 py-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <CardTitle className="text-base font-semibold uppercase tracking-wider text-white">
                        Последние отзывы
                      </CardTitle>
                      <p className="mt-1 text-sm text-chrome-400">
                        Последние записи из подключённых источников
                      </p>
                    </div>
                    <Badge variant="secondary" className="whitespace-nowrap">
                      {reviewsTotal} записей
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <DataTable
                    columns={reviewColumns}
                    rows={reviews}
                    getRowKey={(review) => review.id}
                    emptyMessage="Отзывы не найдены"
                  />
                </CardContent>
              </Card>
            </div>
          )}
        </AsyncView>
      </div>
    </DashboardLayout>
  );
}