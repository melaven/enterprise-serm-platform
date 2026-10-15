/**
 * PlanBadge Component
 * Displays current subscription tier in sidebar
 * Compact design with progress bar for limits
 */

import { Crown, Zap } from 'lucide-react';
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getQuotaStatus, type QuotaStatus } from '@/api/services';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

interface PlanBadgeProps {
  /**
   * Custom className
   */
  className?: string;
  
  /**
   * Compact mode (hide progress bars)
   */
  compact?: boolean;
}

// ============================================================================
// Component
// ============================================================================

/**
 * Plan Badge for Sidebar
 * 
 * Shows current tier and usage limits with progress bars
 * 
 * @example
 * ```tsx
 * <PlanBadge className="mt-auto" />
 * ```
 */
export function PlanBadge({ className, compact = false }: PlanBadgeProps) {
  const [quota, setQuota] = useState<QuotaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    async function fetchQuota() {
      try {
        const status = await getQuotaStatus();
        setQuota(status);
      } catch (error) {
        console.error('Failed to fetch quota:', error);
      } finally {
        setLoading(false);
      }
    }
    
    void fetchQuota();
    
    // Refresh every 60 seconds
    const interval = setInterval(fetchQuota, 60_000);
    return () => clearInterval(interval);
  }, []);
  
  if (loading) {
    return (
      <div className={cn('p-4 border-t-2 border-chrome-600 bg-ink-900', className)}>
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-chrome-700 rounded w-2/3" />
          <div className="h-2 bg-chrome-700 rounded" />
        </div>
      </div>
    );
  }
  
  if (!quota) {
    return null;
  }
  
  // Determine plan tier
  const isPro = quota.limits.max_reviews > 100;
  const planName = isPro ? 'Pro' : 'Free';
  const planIcon = isPro ? Crown : Zap;
  const PlanIcon = planIcon;
  
  // Calculate usage percentages
  const reviewsPercent = quota.reviews_usage_percent ?? 0;
  const tokensPercent = quota.tokens_usage_percent ?? 0;
  
  // Determine warning levels
  const reviewsWarning = reviewsPercent >= 90;
  const tokensWarning = tokensPercent >= 90;
  const anyWarning = reviewsWarning || tokensWarning;
  
  return (
    <Link
      to="/billing"
      className={cn(
        'block p-4 border-t-2 border-chrome-600 bg-ink-900 transition-colors hover:bg-ink-950',
        className
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <PlanIcon
            className={cn(
              'h-4 w-4',
              isPro ? 'text-lime' : 'text-chrome-400'
            )}
          />
          <span className="text-sm font-semibold text-white">
            {planName} Plan
          </span>
        </div>
        
        {!isPro && (
          <span className="text-xs text-plum-300 font-medium uppercase tracking-wider">
            Upgrade
          </span>
        )}
      </div>
      
      {!compact && (
        <div className="space-y-3">
          {/* Reviews Progress */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-chrome-500">Reviews</span>
              <span className="text-xs text-chrome-300 tabular-nums">
                {quota.usage.used_reviews} / {quota.limits.max_reviews}
              </span>
            </div>
            
            <div className="h-1 bg-ink-50 rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full transition-all duration-300',
                  reviewsWarning
                    ? 'bg-red-500'
                    : reviewsPercent >= 70
                    ? 'bg-yellow-500'
                    : 'bg-lime'
                )}
                style={{ width: `${Math.min(100, reviewsPercent)}%` }}
              />
            </div>
          </div>
          
          {/* Tokens Progress */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-chrome-500">LLM Tokens</span>
              <span className="text-xs text-chrome-300 tabular-nums">
                {((quota.usage.used_llm_tokens + quota.usage.reserved_llm_tokens) / 1000).toFixed(0)}k / {(quota.limits.max_llm_tokens / 1000).toFixed(0)}k
              </span>
            </div>
            
            <div className="h-1 bg-ink-50 rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full transition-all duration-300',
                  tokensWarning
                    ? 'bg-red-500'
                    : tokensPercent >= 70
                    ? 'bg-yellow-500'
                    : 'bg-lime'
                )}
                style={{ width: `${Math.min(100, tokensPercent)}%` }}
              />
            </div>
          </div>
          
          {/* Warning Message */}
          {anyWarning && !isPro && (
            <p className="text-xs text-red-400 mt-2">
              ⚠️ Approaching limit
            </p>
          )}
        </div>
      )}
    </Link>
  );
}

/**
 * Simple tier badge without progress bars
 */
export function SimplePlanBadge({ className }: { className?: string }) {
  const [isPro, setIsPro] = useState(false);
  
  useEffect(() => {
    async function checkPlan() {
      try {
        const status = await getQuotaStatus();
        setIsPro(status.limits.max_reviews > 100);
      } catch (error) {
        console.error('Failed to check plan:', error);
      }
    }
    
    void checkPlan();
  }, []);
  
  return (
    <Link
      to="/billing"
      className={cn(
        'inline-flex items-center gap-2 px-3 py-1 rounded-sm border-2 transition-colors',
        isPro
          ? 'border-lime bg-lime/10 text-lime hover:bg-lime/20'
          : 'border-chrome-600 bg-ink-900 text-chrome-400 hover:bg-ink-950',
        className
      )}
    >
      {isPro ? (
        <>
          <Crown className="h-3 w-3" />
          <span className="text-xs font-semibold uppercase tracking-wider">Pro</span>
        </>
      ) : (
        <>
          <Zap className="h-3 w-3" />
          <span className="text-xs font-semibold uppercase tracking-wider">Free</span>
        </>
      )}
    </Link>
  );
}
