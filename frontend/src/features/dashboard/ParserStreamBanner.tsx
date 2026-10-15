/**
 * ParserStreamBanner Component
 * Top-level banner для отображения active parser jobs через SSE
 * 
 * Интегрируется в DashboardLayout для глобального отображения
 */

import { X } from 'lucide-react';
import { useParserStream } from '@/hooks/useParserStream';
import { useParser } from '@/store/useAppStore';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface ParserStreamBannerProps {
  /**
   * Custom className
   */
  className?: string;
  
  /**
   * Allow user to dismiss banner
   * @default false
   */
  dismissible?: boolean;
  
  /**
   * Callback on dismiss
   */
  onDismiss?: () => void;
}

/**
 * Global Parser Stream Banner
 * 
 * Shows at the top of Dashboard when parser is active
 * Provides real-time progress via SSE
 * 
 * @example
 * ```tsx
 * // In DashboardLayout.tsx
 * <div className="flex h-screen">
 *   <ParserStreamBanner />
 *   <main>...</main>
 * </div>
 * ```
 */
export function ParserStreamBanner({
  className,
  dismissible = false,
  onDismiss,
}: ParserStreamBannerProps) {
  const { parserJobId, parserStatus } = useParser();
  
  const { isConnected, progress, connectionError } = useParserStream(parserJobId, {
    debug: false, // Disable debug in production
  });
  
  // Don't render if no active job or already completed
  if (
    !parserJobId ||
    parserStatus === 'succeeded' ||
    parserStatus === 'failed' ||
    parserStatus === null
  ) {
    return null;
  }
  
  return (
    <div
      className={cn(
        'relative w-full border-b-2 border-plum-700 bg-gradient-to-r from-ink-900 to-plum-900/20',
        className
      )}
      role="status"
      aria-live="polite"
      aria-label="Parser job progress"
    >
      {/* Background Progress Bar */}
      {progress && (
        <div
          className="absolute inset-0 bg-gradient-to-r from-plum-900/30 to-lime/10 transition-all duration-300"
          style={{
            width: `${progress.percentage}%`,
          }}
        />
      )}
      
      {/* Content */}
      <div className="relative z-10 flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-4">
          {/* Connection Status Indicator */}
          <div className="flex items-center gap-2">
            <div
              className={cn(
                'h-2 w-2 rounded-full',
                isConnected
                  ? 'bg-lime animate-pulse'
                  : connectionError
                  ? 'bg-red-500'
                  : 'bg-chrome-500 animate-pulse'
              )}
              title={
                isConnected
                  ? 'Connected to live stream'
                  : connectionError
                  ? 'Connection error'
                  : 'Connecting...'
              }
            />
            <span className="text-xs font-medium text-chrome-400 uppercase tracking-wide">
              {isConnected ? 'Live Stream' : 'Connecting...'}
            </span>
          </div>
          
          {/* Job Info */}
          <div className="flex items-center gap-3 border-l border-chrome-600 pl-4">
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-white">
                {progress ? progress.stage : 'Parser running...'}
              </span>
              <span className="text-xs text-chrome-400">
                Job ID: {parserJobId.slice(0, 13)}...
              </span>
            </div>
          </div>
          
          {/* Progress Stats */}
          {progress && (
            <div className="flex items-center gap-4 border-l border-chrome-600 pl-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-chrome-500">Progress:</span>
                <span className="text-sm font-semibold text-lime tabular-nums">
                  {progress.percentage.toFixed(1)}%
                </span>
              </div>
              
              <div className="flex items-center gap-2">
                <span className="text-xs text-chrome-500">Reviews:</span>
                <span className="text-sm font-semibold text-white tabular-nums">
                  {progress.current} / {progress.total}
                </span>
              </div>
            </div>
          )}
        </div>
        
        {/* Right Side: Dismiss Button */}
        {dismissible && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onDismiss}
            className="text-chrome-400 hover:text-white hover:bg-ink-800"
            aria-label="Dismiss banner"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
      
      {/* Connection Error Toast */}
      {connectionError && (
        <div className="absolute bottom-0 left-0 right-0 bg-red-900/30 border-t border-red-700 px-6 py-2">
          <p className="text-xs text-red-300">
            ⚠️ {connectionError}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Simplified Parser Status Badge (for compact spaces)
 */
export function ParserStatusBadge() {
  const { parserJobId, parserStatus } = useParser();
  const { isConnected, progress } = useParserStream(parserJobId);
  
  if (!parserJobId || parserStatus === 'succeeded' || parserStatus === 'failed') {
    return null;
  }
  
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-plum-900/30 border border-plum-700">
      <div
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          isConnected ? 'bg-lime animate-pulse' : 'bg-chrome-500'
        )}
      />
      <span className="text-xs font-medium text-chrome-300">
        {progress ? `${progress.percentage.toFixed(0)}%` : 'Processing...'}
      </span>
    </div>
  );
}
