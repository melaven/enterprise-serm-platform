/** Branded flat card surfaces. */

import { cn } from '@/lib/utils';

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Подсветить карточку границей при наведении. */
  hover?: boolean;
  variant?: 'default' | 'elevated' | 'floating' | 'bordered';
}

export function GlassCard({
  children,
  className,
  hover = false,
  variant = 'default',
  ...props
}: GlassCardProps) {
  return (
    <div
      className={cn(
        'rounded-sm border transition-colors duration-200',
        variant === 'default' && 'border-plum-800 bg-plum-900',
        variant === 'elevated' && 'border-plum-700 bg-plum-900',
        variant === 'floating' && 'border-plum-700 bg-ink-900',
        variant === 'bordered' && 'border-chrome-600 bg-transparent',
        hover && 'cursor-pointer hover:border-lime-500',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

/**
 * Card header with a restrained solid accent
 */
export interface GlassCardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Включить solid accent line */
  accent?: boolean;
  /** Цвет accent (lime, purple, crimson) */
  accentColor?: 'lime' | 'purple' | 'crimson';
}

export function GlassCardHeader({
  children,
  className,
  accent = false,
  accentColor = 'lime',
  ...props
}: GlassCardHeaderProps) {
  const accentClasses = {
    lime: 'bg-lime',
    purple: 'bg-plum',
    crimson: 'bg-crimson',
  };

  return (
    <div className={cn('relative', className)} {...props}>
      {accent && (
        <div className={cn('absolute left-0 top-0 h-px w-full', accentClasses[accentColor])} />
      )}
      {children}
    </div>
  );
}

/**
 * Glass Card Content with responsive padding
 */
export function GlassCardContent({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('p-4 sm:p-6', className)} {...props}>
      {children}
    </div>
  );
}

/**
 * Glass Card Footer with responsive padding
 */
export function GlassCardFooter({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 border-t border-plum-800 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-4',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
