import { Link } from 'react-router-dom';

export function BillingPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-black p-6 text-zinc-100">
      <section
        aria-labelledby="billing-title"
        className="w-full max-w-lg border border-zinc-800 bg-zinc-950 p-8"
      >
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-lime">
          Тарифы и оплата
        </p>
        <h1 className="text-2xl font-semibold" id="billing-title">
          Управление подпиской
        </h1>
        <p className="mt-4 text-sm leading-relaxed text-zinc-400">
          Страница оплаты пока не подключена. Чтобы изменить тариф или восстановить
          доступ, обратитесь к администратору организации.
        </p>
        <Link
          className="mt-8 inline-flex bg-lime px-4 py-3 text-sm font-semibold text-black transition-colors hover:bg-lime-600"
          to="/"
        >
          Вернуться в аналитику
        </Link>
      </section>
    </main>
  );
}
