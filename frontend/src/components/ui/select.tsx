import * as React from 'react';
import { cn } from '@/lib/utils';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: Array<{ value: string; label: string }>;
}

/**
 * Плоский select: ink-900 bg, border-ink-700. Фокус — lime рамка.
 * Стиль идентичен Input компоненту
 * Accessibility: native select with keyboard navigation
 */
export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, options, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'h-11 w-full rounded-sm border border-ink-700 bg-ink-900 px-4 text-sm text-ink-100',
        'ring-0 ring-offset-0 shadow-none appearance-none',
        'focus-visible:border-lime focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950',
        'aria-[invalid=true]:border-plum',
        'disabled:cursor-not-allowed disabled:opacity-40',
        'cursor-pointer',
        className,
      )}
      aria-label={props['aria-label'] || 'Select option'}
      {...props}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
);
Select.displayName = 'Select';
