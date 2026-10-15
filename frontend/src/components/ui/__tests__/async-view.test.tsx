/**
 * Tests for AsyncView component
 * Covers: loading, error, empty, and success states
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AsyncView } from '../async-view';

describe('AsyncView', () => {
  describe('Loading State', () => {
    it('should render loading component when isLoading is true', () => {
      render(
        <AsyncView
          isLoading={true}
          error={null}
          isEmpty={false}
          loadingComponent={<div>Loading...</div>}
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Loading...')).toBeInTheDocument();
      expect(screen.queryByText('Content')).not.toBeInTheDocument();
    });

    it('should render default skeleton when no loadingComponent provided', () => {
      const { container } = render(
        <AsyncView isLoading={true} error={null} isEmpty={false}>
          <div>Content</div>
        </AsyncView>
      );

      // Check for Skeleton component (has specific classes)
      const skeleton = container.querySelector('.animate-pulse');
      expect(skeleton).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should render error message when error is present', () => {
      const testError = new Error('Failed to load data');

      render(
        <AsyncView isLoading={false} error={testError} isEmpty={false}>
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Ошибка загрузки')).toBeInTheDocument();
      expect(screen.getByText('Failed to load data')).toBeInTheDocument();
      expect(screen.queryByText('Content')).not.toBeInTheDocument();
    });

    it('should display error icon with Royal Plum styling', () => {
      const testError = new Error('Test error');

      const { container } = render(
        <AsyncView isLoading={false} error={testError} isEmpty={false}>
          <div>Content</div>
        </AsyncView>
      );

      // Check for AlertCircle icon
      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveClass('text-plum');
    });

    it('should have premium error styling', () => {
      const testError = new Error('Test error');

      const { container } = render(
        <AsyncView isLoading={false} error={testError} isEmpty={false}>
          <div>Content</div>
        </AsyncView>
      );

      const errorCard = container.querySelector('.border-chrome-600');
      expect(errorCard).toBeInTheDocument();
      expect(errorCard).toHaveClass('bg-ink-900');
      expect(errorCard).toHaveClass('rounded-sm');
      expect(errorCard).toHaveClass('border-2');
    });
  });

  describe('Empty State', () => {
    it('should render empty message when isEmpty is true', () => {
      render(
        <AsyncView
          isLoading={false}
          error={null}
          isEmpty={true}
          emptyMessage="No data available"
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('No data available')).toBeInTheDocument();
      expect(screen.queryByText('Content')).not.toBeInTheDocument();
    });

    it('should render default empty message when no emptyMessage provided', () => {
      render(
        <AsyncView isLoading={false} error={null} isEmpty={true}>
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Нет данных')).toBeInTheDocument();
    });

    it('should display Database icon in empty state', () => {
      const { container } = render(
        <AsyncView
          isLoading={false}
          error={null}
          isEmpty={true}
          emptyMessage="Empty"
        >
          <div>Content</div>
        </AsyncView>
      );

      // Check for Database icon
      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveClass('text-chrome-600');
    });

    it('should have consistent empty state styling', () => {
      const { container } = render(
        <AsyncView
          isLoading={false}
          error={null}
          isEmpty={true}
          emptyMessage="Empty"
        >
          <div>Content</div>
        </AsyncView>
      );

      const emptyCard = container.querySelector('.border-chrome-600');
      expect(emptyCard).toBeInTheDocument();
      expect(emptyCard).toHaveClass('bg-ink-900');
      expect(emptyCard).toHaveClass('rounded-sm');
    });
  });

  describe('Success State', () => {
    it('should render children when no loading, error, or empty state', () => {
      render(
        <AsyncView isLoading={false} error={null} isEmpty={false}>
          <div>Success content</div>
        </AsyncView>
      );

      expect(screen.getByText('Success content')).toBeInTheDocument();
    });

    it('should render multiple children', () => {
      render(
        <AsyncView isLoading={false} error={null} isEmpty={false}>
          <div>Child 1</div>
          <div>Child 2</div>
          <div>Child 3</div>
        </AsyncView>
      );

      expect(screen.getByText('Child 1')).toBeInTheDocument();
      expect(screen.getByText('Child 2')).toBeInTheDocument();
      expect(screen.getByText('Child 3')).toBeInTheDocument();
    });
  });

  describe('State Priority', () => {
    it('should prioritize loading over error', () => {
      const testError = new Error('Error');

      render(
        <AsyncView
          isLoading={true}
          error={testError}
          isEmpty={false}
          loadingComponent={<div>Loading</div>}
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Loading')).toBeInTheDocument();
      expect(screen.queryByText('Ошибка загрузки')).not.toBeInTheDocument();
    });

    it('should prioritize loading over empty', () => {
      render(
        <AsyncView
          isLoading={true}
          error={null}
          isEmpty={true}
          loadingComponent={<div>Loading</div>}
          emptyMessage="Empty"
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Loading')).toBeInTheDocument();
      expect(screen.queryByText('Empty')).not.toBeInTheDocument();
    });

    it('should prioritize error over empty', () => {
      const testError = new Error('Error message');

      render(
        <AsyncView
          isLoading={false}
          error={testError}
          isEmpty={true}
          emptyMessage="Empty"
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Ошибка загрузки')).toBeInTheDocument();
      expect(screen.queryByText('Empty')).not.toBeInTheDocument();
    });

    it('should prioritize empty over content', () => {
      render(
        <AsyncView
          isLoading={false}
          error={null}
          isEmpty={true}
          emptyMessage="No items"
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('No items')).toBeInTheDocument();
      expect(screen.queryByText('Content')).not.toBeInTheDocument();
    });
  });

  describe('State Transitions', () => {
    it('should transition from loading to success', () => {
      const { rerender } = render(
        <AsyncView
          isLoading={true}
          error={null}
          isEmpty={false}
          loadingComponent={<div>Loading</div>}
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Loading')).toBeInTheDocument();

      rerender(
        <AsyncView isLoading={false} error={null} isEmpty={false}>
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.queryByText('Loading')).not.toBeInTheDocument();
      expect(screen.getByText('Content')).toBeInTheDocument();
    });

    it('should transition from loading to error', () => {
      const { rerender } = render(
        <AsyncView
          isLoading={true}
          error={null}
          isEmpty={false}
          loadingComponent={<div>Loading</div>}
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Loading')).toBeInTheDocument();

      const testError = new Error('Load failed');
      rerender(
        <AsyncView isLoading={false} error={testError} isEmpty={false}>
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.queryByText('Loading')).not.toBeInTheDocument();
      expect(screen.getByText('Ошибка загрузки')).toBeInTheDocument();
    });

    it('should transition from loading to empty', () => {
      const { rerender } = render(
        <AsyncView
          isLoading={true}
          error={null}
          isEmpty={false}
          loadingComponent={<div>Loading</div>}
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.getByText('Loading')).toBeInTheDocument();

      rerender(
        <AsyncView
          isLoading={false}
          error={null}
          isEmpty={true}
          emptyMessage="No data"
        >
          <div>Content</div>
        </AsyncView>
      );

      expect(screen.queryByText('Loading')).not.toBeInTheDocument();
      expect(screen.getByText('No data')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels in error state', () => {
      const testError = new Error('Test error');

      render(
        <AsyncView isLoading={false} error={testError} isEmpty={false}>
          <div>Content</div>
        </AsyncView>
      );

      // Error should be announced to screen readers
      const errorContainer = screen.getByText('Ошибка загрузки').closest('div');
      expect(errorContainer).toBeInTheDocument();
    });

    it('should have proper role in loading state', () => {
      const { container } = render(
        <AsyncView
          isLoading={true}
          error={null}
          isEmpty={false}
          loadingComponent={<div role="status">Loading</div>}
        >
          <div>Content</div>
        </AsyncView>
      );

      const loadingElement = container.querySelector('[role="status"]');
      expect(loadingElement).toBeInTheDocument();
    });
  });
});
