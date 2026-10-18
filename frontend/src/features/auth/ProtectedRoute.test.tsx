import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { tokens } from '@/api/services';
import { ProtectedRoute } from '@/features/auth/ProtectedRoute';
import { useAppStore } from '@/store/useAppStore';

function renderProtectedRoute() {
  return render(
    <MemoryRouter initialEntries={['/private']}>
      <Routes>
        <Route
          path="/private"
          element={
            <ProtectedRoute>
              <div data-testid="protected-content">Dashboard</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div data-testid="login-page">Login</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  tokens.clear();
  useAppStore.getState().invalidateAuth();
});

describe('ProtectedRoute', () => {
  it('does not mount protected content when no token exists', () => {
    useAppStore.setState({
      isAuthenticated: false,
      token: null,
    });

    renderProtectedRoute();

    expect(screen.queryByTestId('protected-content')).toBeNull();
    expect(screen.queryByTestId('login-page')).not.toBeNull();
  });

  it('does not mount protected content when persisted auth has no usable token', () => {
    useAppStore.setState({
      isAuthenticated: true,
      token: 'expired-or-cleared-token',
    });

    renderProtectedRoute();

    expect(screen.queryByTestId('protected-content')).toBeNull();
    expect(screen.queryByTestId('login-page')).not.toBeNull();
  });

  it('does not mount protected content when the store token differs from the usable token', () => {
    const payload = btoa(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 60 * 60 }),
    );
    tokens.set(`header.${payload}.signature`, { persist: false });
    useAppStore.setState({
      isAuthenticated: true,
      token: 'stale-store-token',
    });

    renderProtectedRoute();

    expect(screen.queryByTestId('protected-content')).toBeNull();
    expect(screen.queryByTestId('login-page')).not.toBeNull();
  });

  it('renders protected content with the current usable token', () => {
    const payload = btoa(
      JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 60 * 60 }),
    );
    const token = `header.${payload}.signature`;
    tokens.set(token, { persist: false });
    useAppStore.setState({
      isAuthenticated: true,
      token,
    });

    renderProtectedRoute();

    expect(screen.queryByTestId('protected-content')).not.toBeNull();
    expect(screen.queryByTestId('login-page')).toBeNull();
  });
});
