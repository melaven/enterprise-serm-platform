/**
 * PaywallModal Component
 * Modal для 402 Payment Required errors
 * Seamless upgrade experience with Stripe integration
 */

import { Crown, X, Zap, ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogClose,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

// ============================================================================
// Types
// ============================================================================

interface PaywallModalProps {
  /**
   * Modal visibility
   */
  open: boolean;
  
  /**
   * Close callback
   */
  onClose: () => void;
  
  /**
   * Quota exceeded reason
   */
  reason?: 'parser_limit' | 'review_limit' | 'token_limit';
  
  /**
   * Current usage info
   */
  usage?: {
    used: number;
    limit: number;
  };
}

// ============================================================================
// Constants
// ============================================================================

const REASON_MESSAGES = {
  parser_limit: {
    title: 'Parser Limit Reached',
    description: "You've used all 5 free parser runs this month. Upgrade to Pro for unlimited parsing.",
    icon: '🚀',
  },
  review_limit: {
    title: 'Review Limit Reached',
    description: "You've reached your monthly review limit. Upgrade to Pro for 10,000 reviews per month.",
    icon: '📊',
  },
  token_limit: {
    title: 'LLM Token Limit Reached',
    description: "You've used all your LLM tokens. Upgrade to Pro for 1M tokens per month.",
    icon: '🤖',
  },
};

// ============================================================================
// Component
// ============================================================================

export function PaywallModal({
  open,
  onClose,
  reason = 'parser_limit',
  usage,
}: PaywallModalProps) {
  const navigate = useNavigate();
  const [upgrading, setUpgrading] = useState(false);
  
  const message = REASON_MESSAGES[reason];
  
  /**
   * Redirect to Stripe Checkout
   */
  const handleUpgrade = async () => {
    setUpgrading(true);
    
    try {
      // Call backend to create Stripe Checkout session
      const response = await fetch('/api/v1/billing/create-checkout-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
        },
        body: JSON.stringify({
          price_id: 'price_pro_monthly',
          success_url: `${window.location.origin}/?upgraded=true`,
          cancel_url: window.location.href,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to create checkout session');
      }
      
      const { checkout_url } = await response.json();
      
      // Redirect to Stripe
      window.location.href = checkout_url;
    } catch (error) {
      console.error('Upgrade error:', error);
      toast.error('Failed to start checkout. Please try again.');
      setUpgrading(false);
    }
  };
  
  /**
   * Navigate to billing page
   */
  const handleViewPlans = () => {
    onClose();
    navigate('/billing');
  };
  
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg border-2 border-plum-700 bg-ink-900 p-0">
        {/* Header with gradient */}
        <div className="relative overflow-hidden bg-gradient-to-br from-plum-900 to-ink-900 p-6 border-b-2 border-plum-700">
          <DialogClose asChild>
            <button className="absolute right-4 top-4 text-chrome-400 hover:text-white transition-colors">
              <X className="h-5 w-5" />
              <span className="sr-only">Close</span>
            </button>
          </DialogClose>
          
          <div className="flex items-start gap-4">
            <div className="flex items-center justify-center h-12 w-12 rounded-sm bg-plum-800 text-3xl shrink-0">
              {message.icon}
            </div>
            
            <div className="flex-1">
              <DialogTitle className="text-xl font-bold text-white mb-1">
                {message.title}
              </DialogTitle>
              <p className="text-sm text-chrome-300">
                {message.description}
              </p>
            </div>
          </div>
        </div>
        
        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Usage Display */}
          {usage && (
            <div className="border-2 border-chrome-700 rounded-sm p-4 bg-ink-950">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-chrome-400">Current Usage</span>
                <span className="text-sm font-semibold text-white tabular-nums">
                  {usage.used} / {usage.limit}
                </span>
              </div>
              
              <div className="h-2 bg-ink-50 rounded-full overflow-hidden">
                <div
                  className="h-full bg-red-500"
                  style={{ width: '100%' }}
                />
              </div>
              
              <p className="text-xs text-red-400 mt-2">
                ⚠️ Limit reached
              </p>
            </div>
          )}
          
          {/* Pro Features */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Crown className="h-5 w-5 text-lime" />
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
                Pro Features
              </h3>
            </div>
            
            <ul className="space-y-2">
              {[
                'Unlimited parser runs',
                '10,000 reviews per month',
                '1M LLM tokens per month',
                'Advanced analytics',
                'Priority support 24/7',
                'API access',
              ].map((feature, index) => (
                <li key={index} className="flex items-center gap-2 text-sm text-chrome-300">
                  <Zap className="h-4 w-4 text-lime shrink-0" />
                  {feature}
                </li>
              ))}
            </ul>
          </div>
          
          {/* Pricing */}
          <div className="border-2 border-lime/30 rounded-sm p-4 bg-lime/5">
            <div className="flex items-baseline gap-2 mb-1">
              <span className="text-3xl font-bold text-white">$49</span>
              <span className="text-chrome-400">/month</span>
            </div>
            <p className="text-xs text-chrome-400">
              14-day money-back guarantee
            </p>
          </div>
        </div>
        
        {/* Footer Actions */}
        <div className="border-t-2 border-chrome-700 p-6 bg-ink-950 flex items-center gap-3">
          <Button
            onClick={handleViewPlans}
            variant="outline"
            className="flex-1"
          >
            View All Plans
          </Button>
          
          <Button
            onClick={handleUpgrade}
            disabled={upgrading}
            className="flex-1 bg-lime text-ink-950 hover:bg-lime/90"
          >
            {upgrading ? (
              'Processing...'
            ) : (
              <>
                Upgrade to Pro
                <ArrowRight className="h-4 w-4 ml-1" />
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
