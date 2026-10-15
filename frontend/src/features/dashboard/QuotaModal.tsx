import { useEffect, useState } from 'react';

interface QuotaData {
  used: number | null;
  limit: number | null;
}

const FEATURES = [
  'Безлимитные потоки для парсера',
  'Приоритетная очередь AI',
  'Выделенный SLA',
];

function readQuotaData(detail: unknown): QuotaData {
  if (typeof detail !== 'object' || detail === null) {
    return { used: null, limit: null };
  }

  const data = detail as Record<string, unknown>;
  return {
    used: typeof data.used === 'number' ? data.used : null,
    limit: typeof data.limit === 'number' ? data.limit : null,
  };
}

export function QuotaModal() {
  const [quotaData, setQuotaData] = useState<QuotaData>({ used: null, limit: null });
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleQuotaError = (event: Event) => {
      if (!(event instanceof CustomEvent)) return;
      setQuotaData(readQuotaData(event.detail));
      setIsOpen(true);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsOpen(false);
    };

    window.addEventListener('quota-exceeded', handleQuotaError);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('quota-exceeded', handleQuotaError);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  if (!isOpen) return null;

  const hasQuotaNumbers = quotaData.used !== null && quotaData.limit !== null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 transition-opacity"
      style={{ backdropFilter: 'blur(8px)' }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) setIsOpen(false);
      }}
    >
      <section
        aria-labelledby="quota-modal-title"
        aria-modal="true"
        className="relative w-full max-w-md overflow-hidden border border-gray-100 bg-white text-gray-900"
        role="dialog"
        style={{ borderRadius: '12px', boxShadow: '0 25px 50px -12px rgb(0 0 0 / 0.35)' }}
      >
        <button
          aria-label="Закрыть"
          className="absolute right-4 top-4 z-10 text-white/70 transition-colors hover:text-white"
          onClick={() => setIsOpen(false)}
          type="button"
        >
          <svg aria-hidden="true" fill="none" height="20" viewBox="0 0 24 24" width="20">
            <path d="m18 6-12 12M6 6l12 12" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
          </svg>
        </button>

        <header className="flex flex-col items-center bg-plum p-6 text-white">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-white/10">
            <svg aria-hidden="true" fill="none" height="24" viewBox="0 0 24 24" width="24">
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" className="text-lime" />
              <path d="M12 8v4m0 4h.01" stroke="currentColor" strokeLinecap="round" strokeWidth="2" className="text-lime" />
            </svg>
          </div>
          <h2 className="text-center text-xl font-semibold tracking-tight" id="quota-modal-title">
            {hasQuotaNumbers ? 'Лимит запросов исчерпан' : 'Проблема с оплатой'}
          </h2>
          {hasQuotaNumbers ? (
            <p className="mt-1 text-sm font-medium text-lime">
              {quotaData.used} / {quotaData.limit} операций
            </p>
          ) : null}
        </header>

        <div className="p-6">
          <p className="mb-6 text-center text-sm leading-relaxed text-gray-600">
            {hasQuotaNumbers
              ? 'Вы достигли предела вашего текущего тарифа. Чтобы продолжить использование парсера и AI-аналитики без остановок, обновите подписку.'
              : 'Подписка организации неактивна. Обновите платёжные данные, чтобы продолжить использование сервиса.'}
          </p>

          <ul className="mb-8 space-y-3">
            {FEATURES.map((feature) => (
              <li className="flex items-center text-sm text-gray-700" key={feature}>
                <svg
                  aria-hidden="true"
                  className="mr-3 shrink-0 text-plum"
                  fill="none"
                  height="16"
                  viewBox="0 0 24 24"
                  width="16"
                >
                  <path d="m5 12 4 4L19 6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                </svg>
                {feature}
              </li>
            ))}
          </ul>

          <button
            className="w-full rounded-lg bg-lime px-4 py-3 font-semibold text-black transition-all duration-200 hover:brightness-95"
            onClick={() => {
              setIsOpen(false);
              window.location.href = '/billing';
            }}
            type="button"
          >
            Перейти на тариф Pro
          </button>
        </div>
      </section>
    </div>
  );
}
