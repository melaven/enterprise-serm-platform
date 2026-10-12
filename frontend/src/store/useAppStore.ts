import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import * as api from '../api/services';
import { withErrorHandling } from '../api/errorHandler';

/**
 * Глобальное состояние приложения с Zustand
 * Управляет аутентификацией, отзывами и аналитикой
 */

interface User {
  id: string;
  email: string;
  tenant_id?: string;
}

interface AppState {
  // Auth State
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  
  // Reviews State
  reviews: api.Review[];
  reviewsLoading: boolean;
  reviewsTotal: number;
  
  // Analytics State
  analytics: api.AnalyticsSummary | null;
  analyticsLoading: boolean;
  
  // Parser State
  parserJobId: string | null;
  parserStatus: string | null;
  
  // UI State
  sidebarCollapsed: boolean;
  activeNavItem: string;
  
  // Auth Actions
  login: (token: string, user: User) => void;
  logout: () => Promise<void>;
  performLogin: (email: string, password: string) => Promise<boolean>;
  performRegister: (email: string, password: string, fullName?: string) => Promise<boolean>;
  
  // Data Fetch Actions
  fetchReviews: (params?: { skip?: number; limit?: number; source?: string; sentiment?: string }) => Promise<void>;
  fetchAnalytics: () => Promise<void>;
  startParser: (url: string, maxReviews?: number) => Promise<string | null>;
  
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
    (set, get) => ({
      // Initial State
      isAuthenticated: false,
      user: null,
      token: null,
      reviews: [],
      reviewsLoading: false,
      reviewsTotal: 0,
      analytics: null,
      analyticsLoading: false,
      parserJobId: null,
      parserStatus: null,
      sidebarCollapsed: false,
      activeNavItem: 'overview',
      
      // ============================================================
      // AUTH ACTIONS
      // ============================================================
      
      login: (token: string, user: User) => {
        // Сохраняем токен в localStorage для axios interceptor
        localStorage.setItem('auth_token', token);
        set({ 
          isAuthenticated: true, 
          token, 
          user 
        });
      },
      
      logout: async () => {
        await withErrorHandling(async () => {
          await api.logout();
          localStorage.removeItem('auth_token');
          set({ 
            isAuthenticated: false, 
            token: null, 
            user: null,
            reviews: [],
            analytics: null,
          });
        });
      },
      
      performLogin: async (email: string, password: string): Promise<boolean> => {
        const result = await withErrorHandling(async () => {
          const response = await api.login({ email, password });
          get().login(response.access_token, response.user);
          return true;
        });
        return result ?? false;
      },
      
      performRegister: async (email: string, password: string, fullName?: string): Promise<boolean> => {
        const result = await withErrorHandling(async () => {
          const response = await api.register({ email, password, full_name: fullName });
          get().login(response.access_token, response.user);
          return true;
        });
        return result ?? false;
      },
      
      // ============================================================
      // DATA FETCH ACTIONS
      // ============================================================
      
      fetchReviews: async (params) => {
        set({ reviewsLoading: true });
        await withErrorHandling(async () => {
          const reviews = await api.getReviews(params);
          set({ 
            reviews, 
            reviewsTotal: reviews.length,
            reviewsLoading: false 
          });
        });
        set({ reviewsLoading: false });
      },
      
      fetchAnalytics: async () => {
        set({ analyticsLoading: true });
        await withErrorHandling(async () => {
          const analytics = await api.getAnalyticsSummary();
          set({ analytics, analyticsLoading: false });
        });
        set({ analyticsLoading: false });
      },
      
      startParser: async (url: string, maxReviews?: number): Promise<string | null> => {
        const result = await withErrorHandling(async () => {
          const user = get().user;
          if (!user) {
            throw new Error('Не удалось определить текущую организацию');
          }
          const response = await api.startParserJob({
            url,
            company_id: user.tenant_id ?? user.id,
            limit: maxReviews,
          });
          set({ 
            parserJobId: response.job_id,
            parserStatus: response.status 
          });
          return response.job_id;
        });
        return result ?? null;
      },
      
      // ============================================================
      // UI ACTIONS
      // ============================================================
      
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
  performLogin: state.performLogin,
  performRegister: state.performRegister,
}));

export const useReviews = () => useAppStore((state) => ({
  reviews: state.reviews,
  reviewsLoading: state.reviewsLoading,
  reviewsTotal: state.reviewsTotal,
  fetchReviews: state.fetchReviews,
}));

export const useAnalytics = () => useAppStore((state) => ({
  analytics: state.analytics,
  analyticsLoading: state.analyticsLoading,
  fetchAnalytics: state.fetchAnalytics,
}));

export const useParser = () => useAppStore((state) => ({
  parserJobId: state.parserJobId,
  parserStatus: state.parserStatus,
  startParser: state.startParser,
}));

export const useUI = () => useAppStore((state) => ({
  sidebarCollapsed: state.sidebarCollapsed,
  activeNavItem: state.activeNavItem,
  toggleSidebar: state.toggleSidebar,
  setActiveNavItem: state.setActiveNavItem,
}));
