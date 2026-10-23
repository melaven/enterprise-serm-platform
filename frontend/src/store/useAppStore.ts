import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import * as api from '../api/services';
import * as demoApi from '../api/demoService';
import { tokens } from '../api/services';
import { withErrorHandling } from '../api/errorHandler';

/**
 * Глобальное состояние приложения с Zustand
 * Управляет аутентификацией, отзывами и аналитикой
 * 
 * Поддерживает Demo Mode через demoService (VITE_DEMO_MODE=true)
 */

// Выбор API: Demo Mode или Production
const isDemoMode =
  import.meta.env.VITE_DEMO_MODE === 'true' || import.meta.env.VITE_USE_MOCKS === 'true';
const apiClient = isDemoMode ? demoApi : api;

type User = api.AuthResponse['user'];

interface AppState {
  // Auth State
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  refreshToken: string | null;

  // Reviews State
  reviews: api.Review[];
  reviewsLoading: boolean;
  reviewsTotal: number;
  reviewsPage: number;
  reviewsPageSize: number;
  reviewsTotalPages: number;

  // Analytics State
  dashboard: api.DashboardSummary | null;
  dashboardLoading: boolean;

  // Parser State
  parserJobId: string | null;
  parserStatus: 'queued' | 'in_progress' | 'succeeded' | 'failed' | null;
  parserResult: api.ParserJobResult | null;
  parserError: string | null;

  // UI State
  sidebarCollapsed: boolean;
  activeNavItem: string;

  // Auth Actions
  login: (auth: api.AuthResponse) => void;
  logout: () => Promise<void>;
  invalidateAuth: () => void;
  performLogin: (email: string, password: string) => Promise<boolean>;
  performRegister: (email: string, password: string, fullName?: string) => Promise<boolean>;

  // Data Fetch Actions
  fetchReviews: (params?: {
    page?: number;
    page_size?: number;
    platform?: string;
    sentiment?: string;
    search?: string;
  }) => Promise<void>;
  fetchDashboard: () => Promise<void>;
  startParser: (platform: string, url: string) => Promise<string | null>;
  pollParserStatus: (jobId: string) => Promise<void>;

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
      refreshToken: null,
      reviews: [],
      reviewsLoading: false,
      reviewsTotal: 0,
      reviewsPage: 1,
      reviewsPageSize: 50,
      reviewsTotalPages: 1,
      dashboard: null,
      dashboardLoading: false,
      parserJobId: null,
      parserStatus: null,
      parserResult: null,
      parserError: null,
      sidebarCollapsed: false,
      activeNavItem: 'overview',

      // ============================================================
      // AUTH ACTIONS
      // ============================================================

      login: (auth: api.AuthResponse) => {
        tokens.set(auth.access_token);
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('auth_token');
        }
        set({
          isAuthenticated: true,
          token: auth.access_token,
          refreshToken: auth.refresh_token,
          user: auth.user,
          reviews: [],
          reviewsTotal: 0,
          reviewsPage: 1,
          reviewsPageSize: 50,
          reviewsTotalPages: 1,
          dashboard: null,
          parserJobId: null,
          parserStatus: null,
          parserResult: null,
          parserError: null,
        });
      },

      invalidateAuth: () => {
        tokens.clear();
        set({
          isAuthenticated: false,
          user: null,
          token: null,
          refreshToken: null,
          reviews: [],
          reviewsLoading: false,
          reviewsTotal: 0,
          reviewsPage: 1,
          reviewsPageSize: 50,
          reviewsTotalPages: 1,
          dashboard: null,
          dashboardLoading: false,
          parserJobId: null,
          parserStatus: null,
          parserResult: null,
          parserError: null,
          sidebarCollapsed: false,
          activeNavItem: 'overview',
        });
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('auth_token');
        }
      },

      logout: async () => {
        try {
          await withErrorHandling(async () => apiClient.logout());
        } finally {
          get().invalidateAuth();
          if (typeof localStorage !== 'undefined') {
            localStorage.removeItem('tenable-serm-storage');
          }
        }
      },

      performLogin: async (email: string, password: string): Promise<boolean> => {
        const result = await withErrorHandling(async () => {
          const response = await apiClient.login({ email, password });
          get().login(response);
          return true;
        });
        return result ?? false;
      },

      performRegister: async (email: string, password: string, fullName?: string): Promise<boolean> => {
        const result = await withErrorHandling(async () => {
          const registration: api.RegisterRequest = { email, password };
          if (fullName !== undefined) {
            registration.full_name = fullName;
          }
          await apiClient.register(registration);
          const auth = await apiClient.login({ email, password });
          get().login(auth);
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
          const paginatedData = await apiClient.getReviews(params);
          set({
            reviews: paginatedData.items,
            reviewsTotal: paginatedData.total,
            reviewsPage: paginatedData.page,
            reviewsPageSize: paginatedData.page_size,
            reviewsTotalPages: paginatedData.total_pages,
            reviewsLoading: false
          });
        });
        set({ reviewsLoading: false });
      },

      fetchDashboard: async () => {
        set({ dashboardLoading: true });
        await withErrorHandling(async () => {
          const dashboard = await apiClient.getDashboardSummary();
          set({ dashboard, dashboardLoading: false });
        });
        set({ dashboardLoading: false });
      },

      startParser: async (platform: string, url: string): Promise<string | null> => {
        const result = await withErrorHandling(async () => {
          const response = await apiClient.startParserJob({ platform, url });
          set({
            parserJobId: response.job_id,
            parserStatus: 'queued',
            parserResult: null,
            parserError: null,
          });
          return response.job_id;
        });
        return result ?? null;
      },

      pollParserStatus: async (jobId: string) => {
        await withErrorHandling(async () => {
          const response = await apiClient.getParserJobStatus(jobId);
          set({
            parserStatus: response.state,
            parserResult: response.result,
            parserError: response.error,
          });
        });
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
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        sidebarCollapsed: state.sidebarCollapsed,
        activeNavItem: state.activeNavItem,
      }),
    }
  )
);
// No need for setUnauthorizedHandler - handled by createApiClient onUnauthorized option
// apiClient already has unauthorized handler configured in services.ts

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
  reviewsPage: state.reviewsPage,
  reviewsPageSize: state.reviewsPageSize,
  reviewsTotalPages: state.reviewsTotalPages,
  fetchReviews: state.fetchReviews,
}));

export const useDashboard = () => useAppStore((state) => ({
  dashboard: state.dashboard,
  dashboardLoading: state.dashboardLoading,
  fetchDashboard: state.fetchDashboard,
}));

export const useParser = () => useAppStore((state) => ({
  parserJobId: state.parserJobId,
  parserStatus: state.parserStatus,
  parserResult: state.parserResult,
  parserError: state.parserError,
  startParser: state.startParser,
  pollParserStatus: state.pollParserStatus,
}));

export const useUI = () => useAppStore((state) => ({
  sidebarCollapsed: state.sidebarCollapsed,
  activeNavItem: state.activeNavItem,
  toggleSidebar: state.toggleSidebar,
  setActiveNavItem: state.setActiveNavItem,
}));
