import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { DashboardLayout, DEFAULT_NAV } from '../components/dashboard/DashboardLayout.tsx';
import { ReviewTable, type ReviewRow } from '../features/reviews/ReviewTable.tsx';

/** Пример сборки: каркас + таблица с мок-данными. */
export function ReviewsOverviewPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<ReviewRow | null>(null);
  const active = DEFAULT_NAV.find((item) => item.href === location.pathname)?.id ?? 'reviews';

  return (
    <DashboardLayout
      title="Обзор отзывов"
      activeId={active}
      onNavigate={(id) => {
        const item = DEFAULT_NAV.find((navItem) => navItem.id === id);
        if (item) navigate(item.href);
      }}
    >
      <ReviewTable onSelect={setSelected} />
      <p className="mt-2 text-xs text-gray-500" aria-live="polite">
        {selected ? `Выбран отзыв ${selected.external_id}` : 'Нажмите на строку, чтобы выбрать отзыв.'}
      </p>
    </DashboardLayout>
  );
}

export default ReviewsOverviewPage;
