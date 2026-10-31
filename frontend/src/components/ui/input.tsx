import * as React from 'react';

import { cn } from '@/lib/utils';

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

/**
 * Плоский инпут: zinc-950 / zinc-800. Фокус — мгновенная смена рамки на lime.
 * Фокус обозначен контрастным outline, кольца и тени не используются.
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = 'text', ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        'h-11 w-full rounded-sm border border-ink-700 bg-ink-900 px-4 text-sm text-ink-100',
        'placeholder:text-ink-500',
        'focus-visible:border-lime focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-lime',
        'aria-[invalid=true]:border-plum',
        'disabled:cursor-not-allowed disabled:opacity-40',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
