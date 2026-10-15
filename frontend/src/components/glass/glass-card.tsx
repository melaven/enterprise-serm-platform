/**
 * Glassmorphism Card Component
 * Premium matted glass effect with Royal Plum background
 */

import { cn } from '@/lib/utils';

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Интенсивность blur (sm, md, lg, xl, 2xl) */
  blur?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  /** Уровень прозрачности фона (0-20) */
  opacity?: number;
  /** Включить hover эффект (lift + glow) */
  hover?: boolean;
  /** Включить border glow */
  borderGlow?: boolean;
  /** Варианты стиля */
  variant?: 'default' | 'elevated' | 'floating' | 'bordered';
}

const BLUR_CLASSES = {
  sm: 'backdrop-blur-sm',
  md: 'backdrop-blur-md',
  lg: 'backdrop-blur-lg',
  xl: 'backdrop-blur-xl',
  '2xl': 'backdrop-blur-2xl', // Глубокое размытие для glassmorphism
};

export function GlassCard({
  children,
  className,
  blur = '2xl', // По умолчанию глубокое размытие
  opacity = 5,
  hover = false,
  borderGlow = false,
  variant = 'default',
  ...props
}: GlassCardProps) {
  return (
    <div
      className={cn(
        // Base glass effect: bg-white/5 + глубокое размытие backdrop-blur-2xl + тонкие рамки
        'rounded-sm border transition-all duration-300', // rounded-sm = 2px
        BLUR_CLASSES[blur],
        `bg-white/${opacity}`,
        
        // Border styles: тонкие рамки border-white/10
        variant === 'default' && 'border-white/10',
        variant === 'elevated' && 'border-white/10',
        variant === 'floating' && 'border-white/10',
        variant === 'bordered' && 'border-white/10',
        
        // Border glow effect (только для lime акцентов)
        borderGlow && 'shadow-[0_0_20px_rgba(197,255,74,0.15)]',
        
        // Многослойные глубокие тени (отрывают карточки от черного фона)
        variant === 'default' && [
          'shadow-[0_4px_12px_rgba(0,0,0,0.4),0_8px_32px_rgba(0,0,0,0.3),0_16px_48px_rgba(0,0,0,0.2)]',
        ],
        variant === 'elevated' && [
          'shadow-[0_8px_16px_rgba(0,0,0,0.5),0_16px_40px_rgba(0,0,0,0.4),0_24px_60px_rgba(0,0,0,0.3)]',
        ],
        variant === 'floating' && [
          'shadow-[0_12px_24px_rgba(0,0,0,0.6),0_24px_56px_rgba(0,0,0,0.5),0_32px_80px_rgba(0,0,0,0.4)]',
        ],
        variant === 'bordered' && [
          'shadow-[0_2px_8px_rgba(0,0,0,0.3),0_4px_16px_rgba(0,0,0,0.2)]',
        ],
        
        // Hover effects
        hover && [
          'hover:-translate-y-1',
          'hover:shadow-[0_16px_32px_rgba(0,0,0,0.7),0_32px_64px_rgba(0,0,0,0.6)]',
          'hover:border-white/15',
          'cursor-pointer',
        ],
        
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

/**
 * Glass Card Header with gradient accent
 */
export interface GlassCardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Включить gradient accent line */
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
  // Акцентные линии: тонкие solid линии без градиентов
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
        'flex flex-col gap-3 border-t border-white/10 px-4 py-3 backdrop-blur-2xl sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-4',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
