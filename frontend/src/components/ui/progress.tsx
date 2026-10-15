import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number; // 0-100
  max?: number;
  variant?: 'default' | 'warning' | 'danger';
}

/**
 * Progress Bar с B2B минимализмом
 * - До 80%: Electric Lime (bg-lime)
 * - 80-95%: Warning (bg-yellow-500)
 * - 95%+: Danger (bg-red-500)
 */
export const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, max = 100, variant, ...props }, ref) => {
    const percentage = Math.min(100, Math.max(0, (value / max) * 100));
    
    // Auto-detect variant based on percentage if not provided
    const computedVariant = variant ?? (
      percentage >= 95 ? 'danger' :
      percentage >= 80 ? 'warning' :
      'default'
    );
    
    const barColor = {
      default: 'bg-lime',
      warning: 'bg-yellow-500',
      danger: 'bg-red-500',
    }[computedVariant];

    return (
      <div
        ref={ref}
        className={cn(
          'relative h-3 w-full overflow-hidden rounded-sm bg-ink-900',
          className
        )}
        {...props}
      >
        <div
          className={cn(
            'h-full transition-all duration-500 ease-out',
            barColor
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    );
  }
);
Progress.displayName = 'Progress';
