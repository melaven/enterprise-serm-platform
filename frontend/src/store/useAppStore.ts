import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { QuotaStatus } from '../api/types';

/**
 * Глобальное состояние приложения с Zustand
 * Управляет аутентификацией, квотами и общими настройками
 */

interface User {
  id: string;
  email: string;
  tenant_id: string;
}

interface AppState {
  // Auth State
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  
  // Quotas State
  quotas: QuotaStatus | null;
  quotasLoading: boolean;
  quotasError: string | null;
  
  // UI State
  sidebarCollapsed: boolean;
  activeNavItem: string;
  
  // Auth Actions
  login: (token: string, user: User) => void;
  logout: () => void;
  
  // Quotas Actions
  setQuotas: (quotas: QuotaStatus) => void;
  setQuotasLoading: (loading: boolean) => void;
  setQuotasError: (error: string | null) => void;
  
  // UI Actions
  toggleSidebar: () => void;
  setActiveNavItem: (item: string) => void;
}

/**
 * Главный стор приложения
 * Использует persist middleware для сохранения в localStorage
 */
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Initial State
      isAuthenticated: false,
      user: null,
      token: null,
      quotas: null,
      quotasLoading: false,
      quotasError: null,
      sidebarCollapsed: false,
      activeNavItem: 'overview',
      
      // Auth Actions
      login: (token: string, user: User) => 
        set({ 
          isAuthenticated: true, 
          token, 
          user 
        }),
      
      logout: () => 
        set({ 
          isAuthenticated: false, 
          token: null, 
          user: null,
          quotas: null 
        }),
      
      // Quotas Actions
      setQuotas: (quotas: QuotaStatus) => 
        set({ 
          quotas, 
          quotasLoading: false, 
          quotasError: null 
        }),
      
      setQuotasLoading: (loading: boolean) => 
        set({ quotasLoading: loading }),
      
      setQuotasError: (error: string | null) => 
        set({ 
          quotasError: error, 
          quotasLoading: false 
        }),
      
      // UI Actions
      toggleSidebar: () => 
        set((state) => ({ 
          sidebarCollapsed: !state.sidebarCollapsed 
        })),
      
      setActiveNavItem: (item: string) => 
        set({ activeNavItem: item }),
    }),
    {
      name: 'tenable-serm-storage',
      partialize: (state) => ({
        // Сохраняем только важные данные
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        sidebarCollapsed: state.sidebarCollapsed,
        activeNavItem: state.activeNavItem,
      }),
    }
  )
);

/**
 * Селекторы для оптимизации перерисовок
 */
export const useAuth = () => useAppStore((state) => ({
  isAuthenticated: state.isAuthenticated,
  user: state.user,
  token: state.token,
  login: state.login,
  logout: state.logout,
}));

export const useQuotas = () => useAppStore((state) => ({
  quotas: state.quotas,
  quotasLoading: state.quotasLoading,
  quotasError: state.quotasError,
  setQuotas: state.setQuotas,
  setQuotasLoading: state.setQuotasLoading,
  setQuotasError: state.setQuotasError,
}));

export const useUI = () => useAppStore((state) => ({
  sidebarCollapsed: state.sidebarCollapsed,
  activeNavItem: state.activeNavItem,
  toggleSidebar: state.toggleSidebar,
  setActiveNavItem: state.setActiveNavItem,
}));
