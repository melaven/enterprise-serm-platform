/**
 * ParserStreamIndicator Component
 * Real-time visual feedback для SSE parser stream
 * 
 * FEATURES:
 * - Live progress bar
 * - Connection status indicator
 * - Current stage display
 * - Animated pulsing effect during processing
 */

import { useParserStream } from '@/hooks/useParserStream';
import { useParser } from '@/store/useAppStore';
import { cn } from '@/lib/utils';

interface ParserStreamIndicatorProps {
  /**
   * Custom className
   */
  className?: string;
  
  /**
   * Show detailed progress info
   * @default true
   */
  showDetails?: boolean;
  
  /**
   * Compact mode (smaller UI)
   * @default false
   */
  compact?: boolean;
}

/**
 * Real-time Parser Stream Indicator
 * 
 * Displays connection status and live progress updates via SSE
 * 
 * @example
 * ```tsx
 * <ParserStreamIndicator />
 * ```
 */
export function ParserStreamIndicator({
  className,
  showDetails = true,
  compact = false,
}: ParserStreamIndicatorProps) {
  const { parserJobId, parserStatus } = useParser();
  
  const { isConnected, progress, connectionError } = useParserStream(parserJobId, {
    onComplete: (result) => {
      console.log('[ParserStream] Complete:', result);
    },
    onError: (error) => {
      console.error('[ParserStream] Error:', error);
    },
    debug: import.meta.env.DEV, // Debug logging in development
  });
  
  // Don't render if no active job
  if (!parserJobId || parserStatus === 'succeeded' || parserStatus === 'failed') {
    return null;
  }
  
  // ============================================================================
  // Connection Status Indicator
  // ============================================================================
  
  const connectionStatusDot = (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          'h-2 w-2 rounded-full',
          isConnected
            ? 'bg-lime animate-pulse'
            : connectionError
            ? 'bg-red-500'
            : 'bg-chrome-500'
        )}
        title={
          isConnected
            ? 'Connected to parser stream'
            : connectionError
            ? `Connection error: ${connectionError}`
            : 'Connecting...'
        }
      />
      <span className="text-xs text-chrome-400">
        {isConnected ? 'Live' : connectionError ? 'Error' : 'Connecting...'}
      </span>
    </div>
  );
  
  // ============================================================================
  // Compact Mode
  // ============================================================================
  
  if (compact) {
    return (
      <div className={cn('flex items-center gap-3', className)}>
        {connectionStatusDot}
        {progress && (
          <div className="flex items-center gap-2">
            <div className="h-1 w-20 bg-ink-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-lime transition-all duration-300"
                style={{ width: `${progress.percentage}%` }}
              />
            </div>
            <span className="text-xs text-chrome-400 tabular-nums">
              {progress.percentage}%
            </span>
          </div>
        )}
      </div>
    );
  }
  
  // ============================================================================
  // Full Mode with Details
  // ============================================================================
  
  return (
    <div
      className={cn(
        'border-2 border-plum-700 bg-plum-900/10 rounded-sm p-4',
        className
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          {/* Connection Status */}
          {connectionStatusDot}
          
          {/* Job ID */}
          <span className="text-xs text-chrome-500 font-mono">
            {parserJobId.slice(0, 8)}...
          </span>
        </div>
        
        {/* Current Status */}
        <span className="text-sm text-chrome-300 capitalize">
          {parserStatus?.replace('_', ' ')}
        </span>
      </div>
      
      {/* Progress Bar */}
      {progress && showDetails && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-chrome-400">{progress.stage}</span>
            <span className="text-chrome-300 tabular-nums font-semibold">
              {progress.current} / {progress.total}
            </span>
          </div>
          
          <div className="relative h-2 bg-ink-100 rounded-full overflow-hidden">
            <div
              className={cn(
                'absolute inset-y-0 left-0 transition-all duration-300',
                'bg-gradient-to-r from-lime to-plum-400'
              )}
              style={{ width: `${progress.percentage}%` }}
            >
              {/* Shimmer effect */}
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
            </div>
          </div>
          
          <div className="flex items-center justify-between text-xs">
            <span className="text-chrome-500">Progress</span>
            <span className="text-lime tabular-nums font-semibold">
              {progress.percentage.toFixed(1)}%
            </span>
          </div>
        </div>
      )}
      
      {/* Connection Error */}
      {connectionError && (
        <div className="mt-3 text-xs text-red-400 border-t border-chrome-700 pt-3">
          ⚠️ {connectionError}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Animation Keyframes (add to globals.css or tailwind.config.js)
// ============================================================================

/**
 * Add to tailwind.config.js:
 * 
 * ```js
 * module.exports = {
 *   theme: {
 *     extend: {
 *       keyframes: {
 *         shimmer: {
 *           '0%': { transform: 'translateX(-100%)' },
 *           '100%': { transform: 'translateX(100%)' },
 *         },
 *       },
 *       animation: {
 *         shimmer: 'shimmer 2s infinite',
 *       },
 *     },
 *   },
 * };
 * ```
 */
