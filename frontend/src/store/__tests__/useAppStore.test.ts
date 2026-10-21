import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  setToken: vi.fn(),
  clearTokens: vi.fn(),
}));

vi.mock('@/api/services', () => ({
  login: apiMocks.login,
  register: apiMocks.register,
  logout: apiMocks.logout,
  tokens: {
    set: apiMocks.setToken,
    clear: apiMocks.clearTokens,
  },
}));

vi.mock('@/api/demoService', () => ({
  login: apiMocks.login,
  register: apiMocks.register,
  logout: apiMocks.logout,
}));

import { useAppStore } from '../useAppStore';

const initialState = useAppStore.getState();

function createAuthResponse() {
  return {
    access_token: 'access-token',
    refresh_token: 'refresh-token',
    token_type: 'bearer' as const,
    expires_in: 3600,
    user: {
      id: 'user-123',
      email: 'test@example.com',
      tenant_id: 'tenant-123',
    },
  };
}

describe('useAppStore authentication actions', () => {
  beforeEach(() => {
    useAppStore.setState(initialState, true);
    vi.clearAllMocks();
  });

  it('logs in and updates the user and token state', async () => {
    apiMocks.login.mockResolvedValueOnce(createAuthResponse());
    const { result } = renderHook(() => useAppStore());
    let loginResult: boolean | undefined;

    await act(async () => {
      loginResult = await result.current.performLogin('test@example.com', 'password123');
    });

    expect(loginResult).toBe(true);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(createAuthResponse().user);
    expect(apiMocks.setToken).toHaveBeenCalledWith('access-token');
    expect(apiMocks.login).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'password123',
    });
  });

  it('returns false and leaves the user unauthenticated when login fails', async () => {
    apiMocks.login.mockRejectedValueOnce(new Error('Invalid credentials'));
    const { result } = renderHook(() => useAppStore());
    let loginResult: boolean | undefined;

    await act(async () => {
      loginResult = await result.current.performLogin('wrong@example.com', 'wrong-password');
    });

    expect(loginResult).toBe(false);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('registers a user and logs them in', async () => {
    apiMocks.register.mockResolvedValueOnce({
      id: 'user-new',
      email: 'newuser@example.com',
      tenant_id: 'tenant-new',
      created_at: new Date().toISOString(),
    });
    apiMocks.login.mockResolvedValueOnce({
      ...createAuthResponse(),
      user: {
        id: 'user-new',
        email: 'newuser@example.com',
        tenant_id: 'tenant-new',
      },
    });
    const { result } = renderHook(() => useAppStore());
    let registrationResult: boolean | undefined;

    await act(async () => {
      registrationResult = await result.current.performRegister(
        'newuser@example.com',
        'password123',
        'New User'
      );
    });

    expect(registrationResult).toBe(true);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.email).toBe('newuser@example.com');
    expect(apiMocks.register).toHaveBeenCalledWith({
      email: 'newuser@example.com',
      password: 'password123',
      full_name: 'New User',
    });
    expect(apiMocks.login).toHaveBeenCalledWith({
      email: 'newuser@example.com',
      password: 'password123',
    });
  });

  it('returns false when registration fails', async () => {
    apiMocks.register.mockRejectedValueOnce(new Error('Email already exists'));
    const { result } = renderHook(() => useAppStore());
    let registrationResult: boolean | undefined;

    await act(async () => {
      registrationResult = await result.current.performRegister(
        'existing@example.com',
        'password123',
        'User'
      );
    });

    expect(registrationResult).toBe(false);
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('clears user and tokens when logging out', async () => {
    useAppStore.setState({
      user: {
        id: 'user-123',
        email: 'test@example.com',
        tenant_id: 'tenant-123',
      },
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useAppStore());

    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(apiMocks.logout).toHaveBeenCalledOnce();
    expect(apiMocks.clearTokens).toHaveBeenCalledOnce();
  });
});
