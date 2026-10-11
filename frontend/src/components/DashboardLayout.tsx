import { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { QuotaWidget } from './QuotaWidget';
import { useAuth, useUI } from '../store/useAppStore';

interface DashboardLayoutProps {
  children: ReactNode;
}

type NavigationItem = {
  id: string;
  label: string;
  icon: string;
};

const navigationItems: NavigationItem[] = [
  { id: 'overview', label: 'Обзор', icon: '◆' },
  { id: 'reviews', label: 'Отзывы', icon: '◇' },
  { id: 'analytics', label: 'Аналитика', icon: '◈' },
  { id: 'settings', label: 'Настройки', icon: '◉' },
];

/**
 * Главный макет дашборда
 * Строгий flat-design: боковой сайдбар + хедер + основной контент
 * Без теней, без скруглений, только границы
 */
export const DashboardLayout = ({ children }: DashboardLayoutProps) => {
  const { isAuthenticated, user, logout } = useAuth();
  const { activeNavItem, setActiveNavItem } = useUI();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    localStorage.removeItem('auth_token');
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-ink flex">
      {/* SIDEBAR - Строгий боковой сайдбар */}
      <aside className="w-64 bg-[#0B0B0F] border-r border-[#C9CED6] flex flex-col">
        {/* Logo / Brand */}
        <div className="px-4 py-6 border-b border-chrome-600">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#5A189A] rounded-none flex items-center justify-center">
              <span className="text-white font-bold text-lg">TS</span>
            </div>
            <div>
              <h1 className="text-base font-semibold text-chrome-300">
                Tenable SERM
              </h1>
              <p className="text-[10px] text-chrome-500 uppercase tracking-wider">
                Dashboard
              </p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4">
          <ul className="space-y-1">
            {navigationItems.map((item) => {
              const isActive = activeNavItem === item.id;
              return (
                <li key={item.id}>
                  <button
                    onClick={() => setActiveNavItem(item.id)}
                    className={`
                      w-full flex items-center gap-3 px-3 py-2
                      text-sm font-medium
                      border border-transparent
                      rounded-none
                      transition-colors duration-150
                      ${
                        isActive
                          ? 'text-[#5A189A] bg-[#5A189A]/10 border-[#5A189A]'
                          : 'text-chrome-400 hover:text-chrome-300 hover:bg-chrome-600/10'
                      }
                    `}
                  >
                    <span className="text-lg">{item.icon}</span>
                    <span>{item.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Quota Widget - В нижней части сайдбара */}
        <QuotaWidget />

        {/* User Section */}
        {isAuthenticated && (
          <div className="px-4 py-3 border-t border-chrome-600">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-chrome-300">
                  {user?.email || 'User'}
                </p>
                <p className="text-[10px] text-chrome-500">
                  {user?.tenant_id ? `Tenant: ${user.tenant_id}` : 'Authenticated'}
                </p>
              </div>
              <button
                onClick={handleLogout}
                className="text-[10px] text-chrome-500 hover:text-chrome-300 transition-colors"
              >
                Выход
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col">
        {/* HEADER - Верхняя панель */}
        <header className="h-16 bg-[#0B0B0F] border-b-2 border-[#C9CED6] flex items-center px-6">
          <div className="flex-1 flex items-center justify-between">
            {/* Breadcrumb / Current Page */}
            <div>
              <h2 className="text-lg font-semibold text-chrome-300">
                {navigationItems.find((item) => item.id === activeNavItem)?.label || 'Dashboard'}
              </h2>
              <p className="text-xs text-chrome-500">
                {new Date().toLocaleDateString('ru-RU', { 
                  weekday: 'long', 
                  year: 'numeric', 
                  month: 'long', 
                  day: 'numeric' 
                })}
              </p>
            </div>

            {/* Header Actions */}
            <div className="flex items-center gap-4">
              {/* Status Badge */}
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-[#C5FF4A] rounded-full"></div>
                <span className="text-xs text-chrome-400">System Online</span>
              </div>

              {/* Notifications (placeholder) */}
              <button className="
                w-8 h-8 
                flex items-center justify-center
                text-chrome-400 hover:text-chrome-300
                border border-chrome-600 hover:border-chrome-400
                rounded-none
                transition-colors duration-150
              ">
                <span className="text-sm">🔔</span>
              </button>
            </div>
          </div>
        </header>

        {/* MAIN CONTENT */}
        <main className="flex-1 overflow-auto bg-ink">
          {children}
        </main>

        {/* FOOTER (optional) */}
        <footer className="h-10 bg-[#0B0B0F] border-t border-chrome-600 flex items-center justify-center">
          <p className="text-[10px] text-chrome-500">
            Tenable SERM © 2026 · Design System v1.0 · Утилитарный flat-design
          </p>
        </footer>
      </div>
    </div>
  );
};
