import { BarChart3, Inbox, LogOut, Settings, type LucideIcon } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

import { QuotaWidget, type QuotaWidgetProps } from '@/components/QuotaWidget';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const NAV: readonly NavItem[] = [
  { to: '/', label: 'Аналитика', icon: BarChart3 },
  { to: '/reviews', label: 'Отзывы', icon: Inbox },
  { to: '/settings', label: 'Настройки', icon: Settings },
];

export interface DashboardLayoutProps {
  /** Заголовок текущего экрана в хедере */
  title: string;
  userEmail?: string;
  /** null — квоты загружаются (скелетон) */
  quota: Pick<QuotaWidgetProps, 'llmTokens' | 'reviewsParsed' | 'resetDate'> | null;
  online: boolean;
  onLogout: () => void;
  onUpgrade?: () => void;
  /** Если не передан — рендерится <Outlet /> */
  children?: React.ReactNode;
}

function Logo() {
  return (
    <div className="flex h-16 items-center gap-3 border-b border-zinc-800 px-6">
      <span
        aria-hidden="true"
        className="flex size-8 items-center justify-center rounded-sm bg-plum text-sm font-bold text-white"
      >
        Х
      </span>
      <span className="text-sm font-semibold uppercase tracking-wider text-white">Хиус</span>
    </div>
  );
}

function SidebarNav() {
  return (
    <nav aria-label="Основная навигация" className="flex-1 overflow-y-auto p-4">
      <ul className="space-y-px">
        {NAV.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex h-11 items-center gap-3 rounded-none border-l-2 px-4 text-xs font-semibold uppercase tracking-wider transition-colors',
                  isActive
                    ? 'border-lime bg-zinc-900/50 text-white'
                    : 'border-transparent text-zinc-400 hover:bg-zinc-900/30 hover:text-white',
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className={cn('size-4 shrink-0', isActive && 'text-lime')}
                    strokeWidth={1.75}
                    aria-hidden="true"
                  />
                  {label}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function QuotaSkeleton() {
  return (
    <div className="space-y-6 border-t border-zinc-800 p-6" aria-busy="true" aria-label="Загрузка квот">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-1.5 w-full" />
      <Skeleton className="h-8 w-28" />
      <Skeleton className="h-1.5 w-full" />
    </div>
  );
}

export function DashboardLayout({
  title,
  userEmail,
  quota,
  online,
  onLogout,
  onUpgrade,
  children,
}: DashboardLayoutProps) {
  return (
    <div className="flex h-screen bg-black text-zinc-100">
      <aside className="hidden w-72 shrink-0 flex-col border-r border-zinc-800 bg-black md:flex">
        <Logo />
        <SidebarNav />
        {quota ? (
          <QuotaWidget
            compact
            {...quota}
            onUpgrade={onUpgrade}
            className="border-x-0 border-b-0 border-t border-zinc-800 bg-black"
          />
        ) : (
          <QuotaSkeleton />
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between gap-6 border-b border-zinc-800 bg-black px-8">
          <h1 className="truncate text-xs font-medium uppercase tracking-wider text-zinc-400">{title}</h1>
          <div className="flex items-center gap-6">
            <span className="flex items-center gap-2 text-xs uppercase tracking-wider text-zinc-400">
              <span aria-hidden="true" className={cn('size-2', online ? 'bg-lime' : 'bg-zinc-700')} />
              {online ? 'Онлайн' : 'Офлайн'}
            </span>
            {userEmail ? (
              <span className="hidden truncate text-xs text-zinc-400 sm:inline">{userEmail}</span>
            ) : null}
            <Button variant="outline" size="sm" onClick={onLogout}>
              <LogOut className="size-4" strokeWidth={1.75} aria-hidden="true" />
              Выйти
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-black p-8">{children ?? <Outlet />}</main>
      </div>
    </div>
  );
}
