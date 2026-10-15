import { BarChart3, Inbox, LogOut, Menu, Settings, X, type LucideIcon } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { QuotaWidget, type QuotaWidgetProps } from '@/features/dashboard/QuotaWidget';
import { PlanBadge } from '@/features/billing/PlanBadge';
import { Button } from '@/components/ui/button';
import { QuotaModal } from './QuotaModal';
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
    <div className="flex h-16 items-center gap-3 border-b border-chrome-600 px-6">
      <span
        aria-hidden="true"
        className="flex size-8 items-center justify-center rounded-sm bg-plum text-sm font-bold text-white"
      >
        T
      </span>
      <span className="text-sm font-semibold uppercase tracking-wider text-white">Tenable SERM</span>
    </div>
  );
}

function SidebarNav() {
  return (
    <nav aria-label="Основная навигация" className="flex-1 overflow-y-auto">
      <ul className="space-y-0">
        {NAV.map(({ to, label, icon: Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                isActive
                  ? 'flex items-center gap-3 px-6 py-3 text-sm transition-all duration-200 ease-in-out bg-ink-900 text-white border-l-2 border-lime'
                  : 'flex items-center gap-3 px-6 py-3 text-sm transition-all duration-200 ease-in-out text-chrome-400 hover:text-white hover:bg-ink-950 border-l-2 border-transparent'
              }
            >
              <Icon className="size-5 shrink-0" strokeWidth={1.75} aria-hidden="true" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <>
      <div className="flex h-screen bg-ink text-chrome-300">
        {/* Desktop Sidebar */}
        <aside className="hidden w-72 shrink-0 flex-col border-r border-chrome-600 bg-ink-900 md:flex">
          <Logo />
          <SidebarNav />
          
          {/* Plan Badge with Usage Stats */}
          <PlanBadge />
        </aside>

        {/* Mobile Sidebar Overlay */}
        {mobileMenuOpen && (
          <>
            <div
              className="fixed inset-0 z-40 bg-ink/60 backdrop-blur-sm md:hidden"
              onClick={() => setMobileMenuOpen(false)}
            />
            <aside className="fixed left-0 top-0 z-50 flex h-full w-72 flex-col border-r border-chrome-600 bg-ink-900 md:hidden">
              <div className="flex h-16 items-center justify-between border-b border-chrome-600 px-6">
                <div className="flex items-center gap-3">
                  <span
                    aria-hidden="true"
                    className="flex size-8 items-center justify-center rounded-sm bg-plum text-sm font-bold text-white"
                  >
                    T
                  </span>
                  <span className="text-sm font-semibold uppercase tracking-wider text-white">Tenable SERM</span>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="-m-2 p-2 text-chrome-400 transition-all duration-200 ease-in-out hover:text-white"
                  aria-label="Закрыть меню"
                >
                  <X className="size-5" strokeWidth={1.75} />
                </button>
              </div>
              <SidebarNav />
              
              {/* Plan Badge in Mobile Menu */}
              <PlanBadge />
            </aside>
          </>
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-chrome-600 bg-ink-900 px-4 sm:gap-6 sm:px-6 md:px-8">
            <div className="flex items-center gap-3">
              {/* Mobile Menu Button */}
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="p-2 text-chrome-400 transition-all duration-200 ease-in-out hover:text-white md:hidden"
                aria-label="Открыть меню"
              >
                <Menu className="size-5" strokeWidth={1.75} />
              </button>
              <h1 className="truncate text-xs font-medium uppercase tracking-wider text-chrome-400">{title}</h1>
            </div>
            <div className="flex items-center gap-3 sm:gap-6">
              <span className="flex items-center gap-2 text-xs uppercase tracking-wider text-chrome-400">
                <span aria-hidden="true" className={cn('size-2', online ? 'bg-lime' : 'bg-chrome-700')} />
                <span className="hidden sm:inline">{online ? 'Онлайн' : 'Офлайн'}</span>
              </span>
              {userEmail ? (
                <span className="hidden truncate text-xs text-chrome-400 lg:inline">{userEmail}</span>
              ) : null}
              <Button variant="outline" size="sm" onClick={onLogout} className="shrink-0">
                <LogOut className="size-4" strokeWidth={1.75} aria-hidden="true" />
                <span className="hidden sm:inline">Выйти</span>
              </Button>
            </div>
          </header>

          <main className="flex-1 overflow-y-auto bg-ink-950 p-4 sm:p-6 md:p-8">{children ?? <Outlet />}</main>
        </div>
      </div>
      <QuotaModal />
    </>
  );
}
