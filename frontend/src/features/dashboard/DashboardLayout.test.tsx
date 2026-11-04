import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { queryClient } from '@/lib/react-query';
import { DashboardLayout } from './DashboardLayout';

vi.mock('@/features/billing/PlanBadge', () => ({
  PlanBadge: () => null,
}));

vi.mock('./QuotaModal', () => ({
  QuotaModal: () => null,
}));

function CurrentPath() {
  const { pathname } = useLocation();
  return <span data-testid="current-path">{pathname}</span>;
}

describe('DashboardLayout logout', () => {
  afterEach(() => {
    queryClient.clear();
  });

  it('runs logout and clears query data before navigating to login', () => {
    const onLogout = vi.fn();
    queryClient.setQueryData(['tenant-data'], { companyId: 'tenant-1' });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/dashboard']}>
          <DashboardLayout
            title="Dashboard"
            quota={null}
            online
            onLogout={onLogout}
          />
          <CurrentPath />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }));

    expect(onLogout).toHaveBeenCalledOnce();
    expect(queryClient.getQueryData(['tenant-data'])).toBeUndefined();
    expect(screen.getByTestId('current-path')).toHaveTextContent('/login');
  });
});
