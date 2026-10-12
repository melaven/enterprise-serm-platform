import { cn } from '@/lib/utils';

/** Ссылки перехода вход/регистрация: серые, без подчёркивания, lime при наведении. */
export const AUTH_LINK = 'text-zinc-400 no-underline hover:text-lime';

export const AUTH_LABEL = 'block text-xs font-medium uppercase tracking-wider text-zinc-400';

interface AuthShellProps {
  title: string;
  children: React.ReactNode;
  footer: React.ReactNode;
  className?: string;
}

/** Общий каркас экранов входа/регистрации: центр экрана, Ink, карточка с рамкой Chrome. */
export function AuthShell({ title, children, footer, className }: AuthShellProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-black px-4 py-12">
      <div className={cn('w-full max-w-md border border-zinc-700 bg-black p-10', className)}>
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-sm bg-plum text-sm font-bold text-white"
          >
            Х
          </span>
          <span className="text-sm font-semibold uppercase tracking-wider text-white">Хиус</span>
        </div>
        <h1 className="mt-10 text-xs font-medium uppercase tracking-wider text-zinc-400">{title}</h1>
        <div className="mt-8">{children}</div>
        <p className="mt-8 border-t border-zinc-900 pt-6 text-sm text-zinc-400">{footer}</p>
      </div>
    </main>
  );
}
