/**
 * Flat progress indicators with restrained lime accents
 */

import { cn } from '@/lib/utils';

export interface GlassProgressProps {
  /** Прогресс 0-100 */
  value?: number;
  /** Индетерминированный (пульсация) */
  indeterminate?: boolean;
  /** Размер */
  size?: 'sm' | 'md' | 'lg';
  /** Label текст */
  label?: string;
  /** Показать процент */
  showPercent?: boolean;
  /** Цвет заливки (Tailwind class) */
  fillColor?: string;
  className?: string;
}

const SIZE_CLASSES = {
  sm: 'h-1',
  md: 'h-1.5',
  lg: 'h-2',
};

export function GlassProgress({
  value = 0,
  indeterminate = false,
  size = 'md',
  label,
  showPercent = false,
  fillColor = 'bg-lime',
  className,
}: GlassProgressProps) {
  const percent = Math.min(100, Math.max(0, value));

  return (
    <div className={cn('space-y-2', className)}>
      {(label || showPercent) && (
        <div className="flex items-center justify-between text-xs">
          {label && <span className="font-medium text-zinc-300">{label}</span>}
          {showPercent && !indeterminate && (
            <span className="tabular-nums text-lime">{Math.round(percent)}%</span>
          )}
        </div>
      )}

      <div
        className={cn(
          'relative w-full overflow-hidden rounded-sm', // rounded-sm = 2px
          'bg-ink-900',
          'border border-chrome-700',
          SIZE_CLASSES[size]
        )}
      >
        {indeterminate ? (
          // Индетерминированный loader (без градиентов)
          <div className="absolute inset-0">
            <div
              className={cn('h-full w-1/3 animate-pulse', fillColor)}
              style={{
                animation: 'slide 2s infinite',
              }}
            />
          </div>
        ) : (
          // Детерминированный progress bar (solid цвет)
          <div
            className={cn(
              'h-full transition-all duration-500 ease-out',
              fillColor,
            )}
            style={{ width: `${percent}%` }}
          />
        )}
      </div>

      <style>{`
        @keyframes slide {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(400%);
          }
        }
      `}</style>
    </div>
  );
}

/**
 * Circular Glass Progress (для status indicators)
 */
export interface GlassCircularProgressProps {
  /** Прогресс 0-100 */
  value?: number;
  /** Размер в px */
  size?: number;
  /** Толщина ring */
  strokeWidth?: number;
  /** Показать label внутри */
  label?: string;
  /** Индетерминированный spin */
  indeterminate?: boolean;
  className?: string;
}

export function GlassCircularProgress({
  value = 0,
  size = 120,
  strokeWidth = 8,
  label,
  indeterminate = false,
  className,
}: GlassCircularProgressProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const percent = Math.min(100, Math.max(0, value));
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div
      className={cn('relative inline-flex items-center justify-center', className)}
      style={{ width: size, height: size }}
    >
      <svg
        className={cn(indeterminate && 'animate-spin')}
        width={size}
        height={size}
        style={{ transform: 'rotate(-90deg)' }}
      >
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255, 255, 255, 0.1)"
          strokeWidth={strokeWidth}
        />

        {/* Progress ring - Electric Lime RGB(197, 255, 74) */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgb(197, 255, 74)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={indeterminate ? circumference * 0.75 : offset}
          className="transition-all duration-500 ease-out"
        />
      </svg>

      {/* Center label */}
      {label && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold tabular-nums text-lime">
            {indeterminate ? '...' : `${Math.round(percent)}%`}
          </span>
          {!indeterminate && (
            <span className="text-xs text-zinc-400">{label}</span>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Compact inline progress indicator
 */
export interface GlassProgressInlineProps {
  /** Current step */
  current: number;
  /** Total steps */
  total: number;
  /** Stage label */
  stage?: string;
  className?: string;
}

export function GlassProgressInline({
  current,
  total,
  stage,
  className,
}: GlassProgressInlineProps) {
  const percent = total > 0 ? (current / total) * 100 : 0;

  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-sm border border-chrome-700 bg-ink-900 px-4 py-2',
        className
      )}
    >
      {/* Animated spinner */}
      <div className="size-4 animate-spin rounded-full border-2 border-white/20 border-t-lime" />

      {/* Progress text */}
      <div className="flex items-center gap-2 text-xs">
        <span className="font-medium tabular-nums text-lime">
          {current}/{total}
        </span>
        {stage && <span className="text-zinc-400">{stage}</span>}
        <span className="font-medium tabular-nums text-zinc-400">
          {Math.round(percent)}%
        </span>
      </div>
    </div>
  );
}
