import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { ReviewForm } from '@/features/reviews/ReviewForm';
import { ReviewsList } from '@/features/reviews/ReviewsList';
import { useAppStore } from '@/store/useAppStore';

/**
 * ReviewsPage — Review Management Interface
 *
 * Grid layout with ReviewForm (left) and ReviewsList (right)
 * Design System: ink/chrome/plum/lime palette, rounded-none, no shadows
 */
export function ReviewsPage() {
  const { user, logout } = useAppStore();

  return (
    <DashboardLayout
      title="Review Management"
      userEmail={user?.email}
      quota={null}
      online
      onLogout={logout}
    >
      <div className="space-y-6">
        {/* Page Header */}
        <section className="border-2 border-chrome-600 bg-ink-900 p-6">
          <h1 className="text-2xl font-semibold text-chrome-300">
            Review Management
          </h1>
          <p className="mt-2 text-sm text-chrome-500">
            Управляйте отзывами клиентов: добавляйте новые записи вручную, просматривайте список и выполняйте операции архивации.
          </p>
        </section>

        {/* Grid Layout: Form (left) + List (right) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Review Form */}
          <div className="lg:col-span-1">
            <div className="border-2 border-chrome-600 bg-ink-900 p-6">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-chrome-300">
                  Добавить отзыв
                </h2>
                <p className="mt-1 text-xs text-chrome-500">
                  Введите данные отзыва для ручного добавления в систему
                </p>
              </div>
              <ReviewForm
                onSuccess={() => {
                  // Optional: show success notification or trigger refresh
                }}
              />
            </div>
          </div>

          {/* Right Column: Reviews List */}
          <div className="lg:col-span-2">
            <div className="border-2 border-chrome-600 bg-ink-900 p-6">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-chrome-300">
                  Список отзывов
                </h2>
                <p className="mt-1 text-xs text-chrome-500">
                  Просмотр и управление существующими отзывами
                </p>
              </div>
              <ReviewsList />
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
