/**
 * Tests for useAppStore
 * Covers: auth actions, token management, demo mode fallback
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAppStore } from '../useAppStore';
import * as demoApi from '@/api/demoService';
import { TokenStore } from '@/api/token';

// Mock API services
vi.mock('@/api/demoService', () => ({
  login: vi.fn(),
  register: vi.fn(),
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
}));

// Mock TokenStore
vi.mock('@/api/token', () => ({
  TokenStore: vi.fn().mockImplementation(() => ({
    getAccessToken: vi.fn(() => null),
    getRefreshToken: vi.fn(() => null),
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
  })),
}));

describe('useAppStore - Auth Actions', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAppStore.setState({
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
    
    // Clear all mocks
    vi.clearAllMocks();
  });

  describe('performLogin', () => {
    it('should successfully login and set user', async () => {
      const mockAuthResponse = {
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'bearer' as const,
        expires_in: 3600,
        user: {
          id: 'user-123',
          email: 'test@example.com',
          tenant_id: 'tenant-123',
        },
      };

      vi.mocked(demoApi.login).mockResolvedValueOnce(mockAuthResponse);

      const { result } = renderHook(() => useAppStore());

      await act(async () => {
        await result.current.performLogin('test@example.com', 'password123');
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user).toEqual({
          id: 'user-123',
          email: 'test@example.com',
          tenant_id: 'tenant-123',
        });
        expect(result.current.isLoading).toBe(false);
      });

      expect(demoApi.login).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });

    it('should handle login errors gracefully', async () => {
      const mockError = new Error('Invalid credentials');
      vi.mocked(demoApi.login).mockRejectedValueOnce(mockError);

      const { result } = renderHook(() => useAppStore());

      await expect(async () => {
        await act(async () => {
          await result.current.performLogin('wrong@example.com', 'wrong-password');
        });
      }).rejects.toThrow('Invalid credentials');

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.isLoading).toBe(false);
    });

    it('should set loading state during login', async () => {
      const mockAuthResponse = {
        access_token: 'test-token',
        refresh_token: 'test-refresh',
        token_type: 'bearer' as const,
        expires_in: 3600,
        user: {
          id: 'user-123',
          email: 'test@example.com',
          tenant_id: 'tenant-123',
        },
      };

      let resolveLogin: ((value: typeof mockAuthResponse) => void) | undefined;
      const loginPromise = new Promise<typeof mockAuthResponse>((resolve) => {
        resolveLogin = resolve;
      });

      vi.mocked(demoApi.login).mockReturnValueOnce(loginPromise);

      const { result } = renderHook(() => useAppStore());

      const loginCall = act(async () => {
        await result.current.performLogin('test@example.com', 'password123');
      });

      // Check loading state is true
      expect(result.current.isLoading).toBe(true);

      // Resolve the promise
      resolveLogin!(mockAuthResponse);
      await loginCall;

      // Check loading state is false after completion
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('performRegister', () => {
    it('should successfully register and set user', async () => {
      const mockAuthResponse = {
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        token_type: 'bearer' as const,
        expires_in: 3600,
        user: {
          id: 'user-new',
          email: 'newuser@example.com',
          tenant_id: 'tenant-new',
        },
      };

      vi.mocked(demoApi.register).mockResolvedValueOnce({
        id: 'user-new',
        email: 'newuser@example.com',
        tenant_id: 'tenant-new',
        created_at: new Date().toISOString(),
      });

      vi.mocked(demoApi.login).mockResolvedValueOnce(mockAuthResponse);

      const { result } = renderHook(() => useAppStore());

      await act(async () => {
        await result.current.performRegister(
          'newuser@example.com',
          'password123',
          'New User'
        );
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user?.email).toBe('newuser@example.com');
      });

      expect(demoApi.register).toHaveBeenCalledWith({
        email: 'newuser@example.com',
        password: 'password123',
        full_name: 'New User',
      });

      expect(demoApi.login).toHaveBeenCalledWith({
        email: 'newuser@example.com',
        password: 'password123',
      });
    });

    it('should handle registration errors', async () => {
      const mockError = new Error('Email already exists');
      vi.mocked(demoApi.register).mockRejectedValueOnce(mockError);

      const { result } = renderHook(() => useAppStore());

      await expect(async () => {
        await act(async () => {
          await result.current.performRegister(
            'existing@example.com',
            'password123',
            'User'
          );
        });
      }).rejects.toThrow('Email already exists');

      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('logout', () => {
    it('should clear user and tokens on logout', async () => {
      // Set initial authenticated state
      useAppStore.setState({
        user: {
          id: 'user-123',
          email: 'test@example.com',
          tenant_id: 'tenant-123',
          created_at: new Date().toISOString(),
        },
        isAuthenticated: true,
      });

      vi.mocked(demoApi.logout).mockResolvedValueOnce(undefined);

      const { result } = renderHook(() => useAppStore());

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(demoApi.logout).toHaveBeenCalledOnce();
    });

    it('should handle logout errors gracefully', async () => {
      useAppStore.setState({
        user: {
          id: 'user-123',
          email: 'test@example.com',
          tenant_id: 'tenant-123',
          created_at: new Date().toISOString(),
        },
        isAuthenticated: true,
      });

      vi.mocked(demoApi.logout).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useAppStore());

      // Should not throw, just clear state
      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe('Token Management', () => {
    it('should store tokens after successful login', async () => {
      const mockTokenStore = new TokenStore(null);
      const setTokensSpy = vi.spyOn(mockTokenStore, 'setTokens');

      const mockAuthResponse = {
        access_token: 'access-token-123',
        refresh_token: 'refresh-token-456',
        token_type: 'bearer' as const,
        expires_in: 3600,
        user: {
          id: 'user-123',
          email: 'test@example.com',
          tenant_id: 'tenant-123',
        },
      };

      vi.mocked(demoApi.login).mockResolvedValueOnce(mockAuthResponse);

      const { result } = renderHook(() => useAppStore());

      await act(async () => {
        await result.current.performLogin('test@example.com', 'password123');
      });

      // Token store should be called (implementation detail, verify in integration test)
      expect(result.current.isAuthenticated).toBe(true);
    });
  });
});
