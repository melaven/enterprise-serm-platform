/**
 * BillingPage Component
 * Minimalist B2B billing interface в стиле Ink-950
 * 
 * Features:
 * - Two-tier pricing (Free & Pro)
 * - Current plan indicator
 * - Stripe Checkout integration
 * - Usage limits display
 */

import { useState, useEffect } from 'react';
import { Check, Crown, ArrowRight, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { DashboardLayout } from '@/features/dashboard/DashboardLayout';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store/useAppStore';
import { getQuotaStatus } from '@/api/services';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

// ============================================================================
// Types
// ============================================================================

interface PricingTier {
  id: 'free' | 'pro';
  name: string;
  price: number;
  currency: string;
  interval: 'month';
  features: string[];
  limits: {
    parser_runs: number;
    llm_tokens: number;
    reviews: number;
  };
  recommended?: boolean;
  cta: string;
}

// ============================================================================
// Pricing Data
// ============================================================================

const PRICING_TIERS: PricingTier[] = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    currency: 'USD',
    interval: 'month',
    features: [
      'До 5 запусков парсера',
      '100 отзывов в месяц',
      '50,000 LLM токенов',
      'Базовая аналитика',
      'Email поддержка',
    ],
    limits: {
      parser_runs: 5,
      llm_tokens: 50_000,
      reviews: 100,
    },
    cta: 'Current Plan',
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 49,
    currency: 'USD',
    interval: 'month',
    features: [
      'Неограниченные запуски',
      '10,000 отзывов в месяц',
      '1,000,000 LLM токенов',
      'Расширенная аналитика',
      'Priority поддержка 24/7',
      'Экспорт в CSV/Excel',
      'API доступ',
      'Custom интеграции',
    ],
    limits: {
      parser_runs: -1, // unlimited
      llm_tokens: 1_000_000,
      reviews: 10_000,
    },
    recommended: true,
    cta: 'Upgrade to Pro',
  },
];

// ============================================================================
// Components
// ============================================================================

/**
 * Pricing Tier Card
 */
interface PricingCardProps {
  tier: PricingTier;
  current: boolean;
  onUpgrade: (tierId: string) => void;
  loading: boolean;
}

function PricingCard({ tier, current, onUpgrade, loading }: PricingCardProps) {
  const isUpgrade = tier.id === 'pro' && !current;
  
  return (
    <div
      className={cn(
        'relative flex flex-col border-2 rounded-sm p-6 transition-all duration-200',
        current
          ? 'border-lime bg-plum-900/20'
          : tier.recommended
          ? 'border-plum-700 bg-ink-900 hover:border-plum-500'
          : 'border-chrome-600 bg-ink-900 hover:border-chrome-500'
      )}
    >
      {/* Recommended Badge */}
      {tier.recommended && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 px-3 py-1 bg-plum text-white text-xs font-semibold uppercase tracking-wider rounded-sm">
          <Crown className="h-3 w-3" />
          Recommended
        </div>
      )}
      
      {/* Current Plan Badge */}
      {current && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 px-3 py-1 bg-lime text-ink-950 text-xs font-semibold uppercase tracking-wider rounded-sm">
          <Check className="h-3 w-3" />
          Current Plan
        </div>
      )}
      
      {/* Header */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white mb-2">
          {tier.name}
        </h3>
        
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold text-white">
            ${tier.price}
          </span>
          <span className="text-chrome-400">
            /{tier.interval}
          </span>
        </div>
      </div>
      
      {/* Features */}
      <ul className="space-y-3 mb-8 flex-1">
        {tier.features.map((feature, index) => (
          <li key={index} className="flex items-start gap-2 text-sm">
            <Check className="h-4 w-4 text-lime shrink-0 mt-0.5" />
            <span className="text-chrome-300">{feature}</span>
          </li>
        ))}
      </ul>
      
      {/* CTA Button */}
      <Button
        onClick={() => onUpgrade(tier.id)}
        disabled={current || loading}
        variant={isUpgrade ? 'default' : 'outline'}
        className={cn(
          'w-full',
          isUpgrade && 'bg-lime text-ink-950 hover:bg-lime/90'
        )}
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing...
          </>
        ) : current ? (
          'Current Plan'
        ) : isUpgrade ? (
          <>
            {tier.cta}
            <ArrowRight className="h-4 w-4 ml-1" />
          </>
        ) : (
          tier.cta
        )}
      </Button>
    </div>
  );
}

/**
 * Usage Stats Component
 */
interface UsageStatsProps {
  stats: {
    reviews_used: number;
    reviews_limit: number;
    tokens_used: number;
    tokens_limit: number;
  } | null;
}

function UsageStats({ stats }: UsageStatsProps) {
  if (!stats) {
    return (
      <div className="border-2 border-chrome-600 rounded-sm p-6 bg-ink-900">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-chrome-700 rounded w-1/3" />
          <div className="h-2 bg-chrome-700 rounded" />
          <div className="h-2 bg-chrome-700 rounded w-2/3" />
        </div>
      </div>
    );
  }
  
  const reviewsPercent = (stats.reviews_used / stats.reviews_limit) * 100;
  const tokensPercent = (stats.tokens_used / stats.tokens_limit) * 100;
  
  return (
    <div className="border-2 border-chrome-600 rounded-sm p-6 bg-ink-900">
      <h3 className="text-lg font-semibold text-white mb-6">
        Current Usage
      </h3>
      
      {/* Reviews Usage */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-chrome-400">Reviews Parsed</span>
          <span className="text-sm font-semibold text-white tabular-nums">
            {stats.reviews_used.toLocaleString()} / {stats.reviews_limit.toLocaleString()}
          </span>
        </div>
        
        <div className="h-2 bg-ink-50 rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-300',
              reviewsPercent >= 90
                ? 'bg-red-500'
                : reviewsPercent >= 70
                ? 'bg-yellow-500'
                : 'bg-lime'
            )}
            style={{ width: `${Math.min(100, reviewsPercent)}%` }}
          />
        </div>
        
        {reviewsPercent >= 90 && (
          <p className="text-xs text-red-400 mt-2">
            ⚠️ Approaching limit - consider upgrading
          </p>
        )}
      </div>
      
      {/* LLM Tokens Usage */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-chrome-400">LLM Tokens Used</span>
          <span className="text-sm font-semibold text-white tabular-nums">
            {stats.tokens_used.toLocaleString()} / {stats.tokens_limit.toLocaleString()}
          </span>
        </div>
        
        <div className="h-2 bg-ink-50 rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-300',
              tokensPercent >= 90
                ? 'bg-red-500'
                : tokensPercent >= 70
                ? 'bg-yellow-500'
                : 'bg-lime'
            )}
            style={{ width: `${Math.min(100, tokensPercent)}%` }}
          />
        </div>
        
        {tokensPercent >= 90 && (
          <p className="text-xs text-red-400 mt-2">
            ⚠️ Approaching limit - consider upgrading
          </p>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function BillingPage() {
  const { user, logout } = useAppStore();
  
  const [currentPlan, setCurrentPlan] = useState<'free' | 'pro'>('free');
  const [loading, setLoading] = useState(false);
  const [usageStats, setUsageStats] = useState<UsageStatsProps['stats']>(null);
  
  // Fetch current quota status
  useEffect(() => {
    async function fetchQuotaStatus() {
      try {
        const status = await getQuotaStatus();
        
        // Determine current plan based on limits
        const isPro = status.limits.max_reviews > 100;
        setCurrentPlan(isPro ? 'pro' : 'free');
        
        setUsageStats({
          reviews_used: status.usage.used_reviews,
          reviews_limit: status.limits.max_reviews,
          tokens_used: status.usage.used_llm_tokens + status.usage.reserved_llm_tokens,
          tokens_limit: status.limits.max_llm_tokens,
        });
      } catch (error) {
        console.error('Failed to fetch quota status:', error);
        toast.error('Failed to load usage data');
      }
    }
    
    void fetchQuotaStatus();
  }, []);
  
  /**
   * Handle upgrade to Pro
   * Redirects to Stripe Checkout
   */
  const handleUpgrade = async (tierId: string) => {
    if (tierId === 'free') {
      toast.info('You are already on the Free plan');
      return;
    }
    
    if (tierId === 'pro') {
      setLoading(true);
      
      try {
        // Call backend to create Stripe Checkout session
        const response = await fetch('/api/v1/billing/create-checkout-session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          },
          body: JSON.stringify({
            price_id: 'price_pro_monthly', // Stripe Price ID
            success_url: `${window.location.origin}/billing?session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${window.location.origin}/billing`,
          }),
        });
        
        if (!response.ok) {
          throw new Error('Failed to create checkout session');
        }
        
        const { checkout_url } = await response.json();
        
        // Redirect to Stripe Checkout
        window.location.href = checkout_url;
      } catch (error) {
        console.error('Upgrade error:', error);
        toast.error('Failed to start checkout. Please try again.');
        setLoading(false);
      }
    }
  };
  
  return (
    <DashboardLayout
      title="Billing & Subscriptions"
      userEmail={user?.email}
      quota={null} // Hide quota widget on billing page
      online={true}
      onLogout={() => void logout()}
    >
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            Choose Your Plan
          </h1>
          <p className="text-chrome-400">
            Upgrade to Pro for unlimited parsing and advanced features
          </p>
        </div>
        
        {/* Usage Stats */}
        <div className="mb-8">
          <UsageStats stats={usageStats} />
        </div>
        
        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-6 mb-12">
          {PRICING_TIERS.map((tier) => (
            <PricingCard
              key={tier.id}
              tier={tier}
              current={currentPlan === tier.id}
              onUpgrade={handleUpgrade}
              loading={loading}
            />
          ))}
        </div>
        
        {/* FAQ Section */}
        <div className="border-2 border-chrome-600 rounded-sm p-6 bg-ink-900">
          <h3 className="text-lg font-semibold text-white mb-4">
            Frequently Asked Questions
          </h3>
          
          <div className="space-y-4">
            <div>
              <h4 className="text-sm font-semibold text-white mb-1">
                Can I cancel anytime?
              </h4>
              <p className="text-sm text-chrome-400">
                Yes, you can cancel your Pro subscription at any time. Your access will continue until the end of your billing period.
              </p>
            </div>
            
            <div>
              <h4 className="text-sm font-semibold text-white mb-1">
                What happens when I reach my limit?
              </h4>
              <p className="text-sm text-chrome-400">
                On the Free plan, you'll receive a notification and won't be able to start new parser runs until the next billing cycle or upgrade to Pro.
              </p>
            </div>
            
            <div>
              <h4 className="text-sm font-semibold text-white mb-1">
                Is there a trial period for Pro?
              </h4>
              <p className="text-sm text-chrome-400">
                Pro plan includes a 14-day money-back guarantee. If you're not satisfied, contact support for a full refund.
              </p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
