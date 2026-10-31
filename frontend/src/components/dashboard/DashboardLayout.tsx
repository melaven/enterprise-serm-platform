import { useState, type MouseEvent, type ReactNode } from 'react';
import { BarChart3, Database, Menu, MessageSquare, Settings, X, type LucideIcon } from 'lucide-react';

export interface NavItem {
  readonly id: string;
  readonly label: string;
  readonly href: string;
  readonly icon: LucideIcon;
}

export const DEFAULT_NAV: readonly NavItem[] = [
  { id: 'reviews', label: 'Отзывы', href: '/reviews/overview', icon: MessageSquare },
  { id: 'analytics', label: 'Аналитика', href: '/dashboard', icon: BarChart3 },
  { id: 'sources', label: 'Источники', href: '/reviews', icon: Database },
  { id: 'settings', label: 'Настройки', href: '/settings', icon: Settings },
];

interface DashboardLayoutProps {
  readonly title: string;
  readonly children: ReactNode;
  readonly navItems?: readonly NavItem[];
  readonly activeId?: string;
  /** Если передан, клик по пункту не переходит по href (для SPA-роутинга вызывающей стороной). */
  readonly onNavigate?: (id: string) => void;
  readonly organization?: string;
}

const FOCUS = 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-gray-900';

/** Каркас кабинета Tenable: боковое меню (на мобильных выезжает), шапка, контент. Только gray-палитра, без теней. */
export function DashboardLayout({
  title,
  children,
  navItems = DEFAULT_NAV,
  activeId,
  onNavigate,
  organization = 'Организация',
}: DashboardLayoutProps) {
  const [open, setOpen] = useState(false);

  const menu = (
    <nav aria-label="Основная навигация" className="flex-1 py-2">
      <ul>
        {navItems.map((item) => {
          const active = item.id === activeId;
          const Icon = item.icon;
          return (
            <li key={item.id}>
              <a
                href={item.href}
                aria-current={active ? 'page' : undefined}
                onClick={(e: MouseEvent<HTMLAnchorElement>) => {
                  setOpen(false);
                  if (onNavigate) {
                    e.preventDefault();
                    onNavigate(item.id);
                  }
                }}
                className={`flex items-center gap-2.5 border-l-2 px-3 py-2 text-sm ${FOCUS} ${
                  active
                    ? 'border-gray-900 bg-gray-100 font-medium text-gray-900'
                    : 'border-transparent text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                {item.label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );

  const sidebar = (
    <div className="flex h-full w-60 flex-col border-r border-gray-200 bg-white">
      <div className="flex h-12 items-center border-b border-gray-200 px-3">
        <span className="text-base font-bold tracking-tight text-gray-900">Tenable</span>
      </div>
      {menu}
      <div className="border-t border-gray-200 px-3 py-2">
        <div className="text-[11px] uppercase tracking-wide text-gray-500">Организация</div>
        <div className="mt-0.5 truncate text-sm text-gray-900">{organization}</div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded-sm focus:border focus:border-gray-200 focus:bg-white focus:px-3 focus:py-2"
      >
        К содержимому
      </a>

      {/* Десктоп: фиксированный сайдбар */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden md:block">{sidebar}</aside>

      {/* Мобильный: выдвижное меню */}
      {open ? (
        <div className="fixed inset-0 z-30 md:hidden">
          <button
            type="button"
            aria-label="Закрыть меню"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-gray-900/40"
          />
          <div className="relative h-full w-60">{sidebar}</div>
        </div>
      ) : null}

      <div className="md:pl-60">
        <header className="sticky top-0 z-10 flex h-12 items-center gap-3 border-b border-gray-200 bg-white px-3">
          <button
            type="button"
            aria-label="Открыть меню"
            aria-expanded={open}
            onClick={() => setOpen(true)}
            className={`rounded-sm border border-gray-200 p-1.5 text-gray-700 hover:bg-gray-50 md:hidden ${FOCUS}`}
          >
            {open ? <X aria-hidden="true" className="h-4 w-4" /> : <Menu aria-hidden="true" className="h-4 w-4" />}
          </button>
          <h1 className="text-sm font-semibold text-gray-900">{title}</h1>
        </header>
        <main id="main" tabIndex={-1} className="p-3 md:p-4">
          {children}
        </main>
      </div>
    </div>
  );
}

export default DashboardLayout;
