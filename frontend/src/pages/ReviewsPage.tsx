import { useState } from 'react';
import { toast } from 'sonner';

import { DashboardLayout } from '@/components/DashboardLayout';
import { ReviewsTable } from '@/components/ReviewsTable';
import { Button } from '@/components/ui/button';
import { useAppStore, useParser } from '@/store/useAppStore';

const DEFAULT_PARSER_URL = 'https://2gis.ru/moscow/firm/70000001012345678/tab/reviews';

export function ReviewsPage() {
  const { user, logout } = useAppStore();
  const { startParser } = useParser();
  const [url, setUrl] = useState(DEFAULT_PARSER_URL);
  const [isStarting, setIsStarting] = useState(false);

  const handleStartParser = async () => {
    setIsStarting(true);
    try {
      const jobId = await startParser(url, 50);
      if (jobId) {
        toast.success('Сбор данных запущен', {
          description: `Задача ${jobId} добавлена в очередь`,
        });
      }
    } finally {
      setIsStarting(false);
    }
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
        <section className="card space-y-4 p-6">
          <div>
            <h2 className="text-xl font-semibold text-chrome-300">Сбор данных</h2>
            <p className="mt-1 text-sm text-chrome-500">
              Запустите парсинг отзывов. При исчерпанной квоте API вернёт 402.
            </p>
          </div>
          <label className="block space-y-2">
            <span className="text-label">Ссылка на страницу 2GIS</span>
            <input
              className="input-field w-full"
              onChange={(event) => setUrl(event.target.value)}
              type="url"
              value={url}
            />
          </label>
          <Button disabled={isStarting || !url.trim()} onClick={handleStartParser}>
            {isStarting ? 'Запускаем…' : 'Запустить сбор данных'}
          </Button>
        </section>

        <ReviewsTable />
      </div>
    </DashboardLayout>
  );
}
