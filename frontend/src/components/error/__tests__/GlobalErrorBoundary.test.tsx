/**
 * Tests for GlobalErrorBoundary
 * Covers: error catching, error screen rendering, recovery actions
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GlobalErrorBoundary } from '../GlobalErrorBoundary';

// Component that throws an error
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error: Component crashed');
  }
  return <div>Component rendered successfully</div>;
}

describe('GlobalErrorBoundary', () => {
  // Suppress console.error during tests
  const originalConsoleError = console.error;
  
  beforeEach(() => {
    console.error = vi.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
    vi.unstubAllEnvs();
  });

  it('should render children when no error occurs', () => {
    render(
      <GlobalErrorBoundary>
        <div>Test content</div>
      </GlobalErrorBoundary>
    );

    expect(screen.getByText('Test content')).toBeInTheDocument();
  });

  it('should catch error and render error screen', () => {
    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    // Check that error screen is rendered
    expect(screen.getByText('Произошла системная ошибка рендеринга')).toBeInTheDocument();
    expect(
      screen.getByText(/Приложение столкнулось с критической ошибкой/i)
    ).toBeInTheDocument();
  });

  it('should display reload button', () => {
    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    const reloadButton = screen.getByRole('button', {
      name: /перезагрузить приложение/i,
    });
    expect(reloadButton).toBeInTheDocument();
  });

  it('should reload page when reload button is clicked', () => {
    const reloadMock = vi.fn();
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { reload: reloadMock },
    });

    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    const reloadButton = screen.getByRole('button', {
      name: /перезагрузить приложение/i,
    });

    fireEvent.click(reloadButton);

    expect(reloadMock).toHaveBeenCalledOnce();
  });

  it('should display support email link', () => {
    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    const emailLink = screen.getByRole('link', {
      name: /support@tenable-serm\.com/i,
    });
    expect(emailLink).toBeInTheDocument();
    expect(emailLink).toHaveAttribute('href', 'mailto:support@tenable-serm.com');
  });

  it('should display error icon with Royal Plum styling', () => {
    const { container } = render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    // Check for AlertTriangle icon (lucide-react renders as svg)
    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass('text-plum');
  });

  it('should have premium error screen styling', () => {
    const { container } = render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    // Check for B2B minimalism classes
    const errorCard = container.querySelector('.border-chrome-600');
    expect(errorCard).toBeInTheDocument();
    expect(errorCard).toHaveClass('bg-ink-900');
    expect(errorCard).toHaveClass('rounded-sm');
    expect(errorCard).toHaveClass('border-2');
  });

  it('should show DEV mode error details in development', () => {
    vi.stubEnv('DEV', true);

    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    // Check for DEV MODE badge
    expect(screen.getByText('DEV MODE')).toBeInTheDocument();
    expect(screen.getByText(/Test error: Component crashed/i)).toBeInTheDocument();

  });

  it('should hide error details in production', () => {
    vi.stubEnv('DEV', false);

    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    // Check that DEV MODE badge is NOT shown
    expect(screen.queryByText('DEV MODE')).not.toBeInTheDocument();
    expect(screen.queryByText(/Test error: Component crashed/i)).not.toBeInTheDocument();

    // But error screen is still shown
    expect(screen.getByText('Произошла системная ошибка рендеринга')).toBeInTheDocument();

  });

  it('should log error to console', () => {
    const consoleErrorSpy = vi.spyOn(console, 'error');

    render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    expect(consoleErrorSpy).toHaveBeenCalled();
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      expect.stringContaining('[GlobalErrorBoundary]'),
      expect.any(Error)
    );
  });

  it('should recover after error reset in DEV mode', () => {
    vi.stubEnv('DEV', true);

    let shouldThrow = true;
    function RecoverableError() {
      if (shouldThrow) {
        throw new Error('Test error: Component crashed');
      }
      return <div>Component rendered successfully</div>;
    }

    render(
      <GlobalErrorBoundary>
        <RecoverableError />
      </GlobalErrorBoundary>
    );

    // Error screen should be shown
    expect(screen.getByText('Произошла системная ошибка рендеринга')).toBeInTheDocument();

    // Click reset button (only available in DEV)
    const resetButton = screen.getByRole('button', {
      name: /попробовать восстановить/i,
    });
    shouldThrow = false;
    fireEvent.click(resetButton);

    expect(screen.getByText('Component rendered successfully')).toBeInTheDocument();

  });

  it('should prevent white screen of death', () => {
    const { container } = render(
      <GlobalErrorBoundary>
        <ThrowError shouldThrow={true} />
      </GlobalErrorBoundary>
    );

    // Container should have content (not empty/white)
    expect(container.firstChild).toBeInTheDocument();
    expect(container.textContent).not.toBe('');
  });
});
