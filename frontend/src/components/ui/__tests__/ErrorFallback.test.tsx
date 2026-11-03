import { fireEvent, render, screen } from '@testing-library/react';
import { ErrorBoundary } from 'react-error-boundary';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ErrorFallback } from '../ErrorFallback';

const mocks = vi.hoisted(() => ({
  onReset: vi.fn(),
}));

function BrokenWidget() {
  throw new Error('Widget render failed');
}

describe('ErrorFallback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a retry button that resets its boundary', () => {
    const shouldThrow = { current: true };
    function RecoverableWidget() {
      if (shouldThrow.current) {
        throw new Error('Widget render failed');
      }
      return <p>Widget recovered</p>;
    }

    render(
      <ErrorBoundary
        FallbackComponent={ErrorFallback}
        onReset={() => {
          shouldThrow.current = false;
          mocks.onReset();
        }}
      >
        <RecoverableWidget />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Something went wrong in this widget',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(screen.getByText('Widget recovered')).toBeInTheDocument();
    expect(mocks.onReset).toHaveBeenCalledOnce();
  });

  it('renders the fallback for a widget error', () => {
    render(
      <ErrorBoundary FallbackComponent={ErrorFallback}>
        <BrokenWidget />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Something went wrong in this widget',
    );
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });
});
