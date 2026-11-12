import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import * as api from '../api/services';
import * as demoApi from '../api/demoService';
import { tokens } from '../api/services';
import { OWN_TOKEN_KEY } from '../api/token';
import { withErrorHandling } from '../api/errorHandler';

/**
 * Глобальное состояние приложения с Zustand
 * Управляет аутентификацией, состоянием парсер-задачи и UI
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
  hardReset: () => void;
  logout: () => Promise<void>;
  invalidateAuth: () => void;
  performLogin: (email: string, password: string) => Promise<boolean>;
  performRegister: (email: string, password: string, fullName?: string) => Promise<boolean>;

  // Parser Actions
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
          refreshToken: auth.refresh_token ?? null,
          user: auth.user ?? null,
          parserJobId: null,
          parserStatus: null,
          parserResult: null,
          parserError: null,
        });
      },

      hardReset: () => {
        tokens.clear();
        set({
          isAuthenticated: false,
          user: null,
          token: null,
          refreshToken: null,
          parserJobId: null,
          parserStatus: null,
          parserResult: null,
          parserError: null,
          sidebarCollapsed: false,
          activeNavItem: 'overview',
        });
        useAppStore.persist.clearStorage();
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem(OWN_TOKEN_KEY);
          localStorage.removeItem('auth_token');
        }
      },

      invalidateAuth: () => {
        get().hardReset();
      },

      logout: async () => {
        const accessToken = tokens.get();
        get().hardReset();
        await withErrorHandling(async () => apiClient.logout(accessToken ?? undefined));
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
      name: 'sentiguard-storage',
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
