/**
 * LandingPage Component
 * Conversion landing page for SERM platform
 * Dark B2B theme with Royal Plum (#5A189A) and Electric Lime (#C5FF4A)
 */

import { ArrowRight, Shield, Zap, BarChart3, Check, Crown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

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
  recommended?: boolean;
  cta: string;
}

// ============================================================================
// Pricing Data (reused from BillingPage)
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
    cta: 'Get Started',
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
    recommended: true,
    cta: 'Start Free Trial',
  },
];

// ============================================================================
// Components
// ============================================================================

/**
 * Pricing Tier Card for Landing Page
 */
interface PricingCardProps {
  tier: PricingTier;
}

function PricingCard({ tier }: PricingCardProps) {
  return (
    <div
      className={cn(
        'relative flex flex-col border-2 rounded-sm p-6 transition-all duration-200',
        tier.recommended
          ? 'border-[#5A189A] bg-[#5A189A]/10 hover:border-[#5A189A]/80'
          : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'
      )}
      style={{
        backgroundColor: tier.recommended ? 'rgba(90, 24, 154, 0.1)' : 'rgba(17, 24, 39, 0.5)',
      }}
    >
      {/* Recommended Badge */}
      {tier.recommended && (
        <div
          className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 px-3 py-1 text-white text-xs font-semibold uppercase tracking-wider rounded-sm"
          style={{ backgroundColor: '#5A189A' }}
        >
          <Crown className="h-3 w-3" />
          Recommended
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white mb-2">{tier.name}</h3>
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold text-white">${tier.price}</span>
          <span className="text-gray-400">/{tier.interval}</span>
        </div>
      </div>

      {/* Features */}
      <ul className="space-y-3 mb-8 flex-1">
        {tier.features.map((feature, index) => (
          <li key={index} className="flex items-start gap-2 text-sm">
            <Check
              className="h-4 w-4 shrink-0 mt-0.5"
              style={{ color: '#C5FF4A' }}
            />
            <span className="text-gray-300">{feature}</span>
          </li>
        ))}
      </ul>

      {/* CTA Button */}
      <Link to="/register">
        <Button
          className={cn(
            'w-full',
            tier.recommended
              ? 'text-black font-semibold hover:opacity-90'
              : 'border-gray-600 text-white hover:bg-gray-800'
          )}
          style={
            tier.recommended
              ? { backgroundColor: '#C5FF4A' }
              : { backgroundColor: 'transparent', borderColor: '#4B5563' }
          }
          variant={tier.recommended ? 'default' : 'outline'}
        >
          {tier.cta}
          <ArrowRight className="h-4 w-4 ml-1" />
        </Button>
      </Link>
    </div>
  );
}

/**
 * Feature Card
 */
interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <div className="border border-gray-700 rounded-sm p-6 bg-gray-900/30 hover:border-[#5A189A]/50 transition-colors">
      <div className="mb-4" style={{ color: '#5A189A' }}>
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-gray-400 text-sm">{description}</p>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950">
      {/* Navigation */}
      <nav className="border-b border-gray-800 bg-gray-950/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <span className="text-xl font-bold text-white">SERM</span>
            </div>
            <div className="flex items-center gap-4">
              <Link to="/login">
                <Button variant="ghost" className="text-gray-300 hover:text-white">
                  Login
                </Button>
              </Link>
              <Link to="/register">
                <Button
                  className="text-black font-semibold hover:opacity-90"
                  style={{ backgroundColor: '#C5FF4A' }}
                >
                  Get Started
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <h1
            className="text-5xl sm:text-6xl font-bold text-white mb-6"
            style={{ lineHeight: 1.2 }}
          >
            Enterprise SERM &{' '}
            <span style={{ color: '#5A189A' }}>Sentiment Intelligence</span>
          </h1>
          <p className="text-xl text-gray-400 mb-8 max-w-3xl mx-auto">
            Автоматический контроль репутации вашего бизнеса с AI-анализом тональности,
            защитой от спама и B2B API для интеграции с CRM
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link to="/register">
              <Button
                size="lg"
                className="text-black font-semibold hover:opacity-90 text-lg px-8"
                style={{ backgroundColor: '#C5FF4A' }}
              >
                Start Free Trial
                <ArrowRight className="h-5 w-5 ml-2" />
              </Button>
            </Link>
            <Link to="/pricing">
              <Button
                size="lg"
                variant="outline"
                className="border-gray-600 text-white hover:bg-gray-800 text-lg px-8"
              >
                View Pricing
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 bg-gray-900/30">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-white mb-4">
              Everything you need to manage reputation
            </h2>
            <p className="text-gray-400 max-w-2xl mx-auto">
              Powerful features for enterprise-grade reputation management
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <FeatureCard
              icon={<BarChart3 className="h-8 w-8" />}
              title="B2B API"
              description="Полноценный REST API для интеграции с вашими CRM и системами автоматизации"
            />
            <FeatureCard
              icon={<Zap className="h-8 w-8" />}
              title="AI-анализ тональности"
              description="Автоматическое определение эмоциональной окраски отзывов powered by LLM"
            />
            <FeatureCard
              icon={<Shield className="h-8 w-8" />}
              title="Защита от спама"
              description="Rate limiting, фильтрация фейковых отзывов и защита от DDoS атак"
            />
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-white mb-4">
              Simple, transparent pricing
            </h2>
            <p className="text-gray-400 max-w-2xl mx-auto">
              Начните бесплатно, масштабируйтесь по мере роста
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {PRICING_TIERS.map((tier) => (
              <PricingCard key={tier.id} tier={tier} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 bg-gray-900/30">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to take control of your reputation?
          </h2>
          <p className="text-gray-400 mb-8">
            Join thousands of companies using SERM to monitor and improve their online presence
          </p>
          <Link to="/register">
            <Button
              size="lg"
              className="text-black font-semibold hover:opacity-90 text-lg px-8"
              style={{ backgroundColor: '#C5FF4A' }}
            >
              Get Started Now
              <ArrowRight className="h-5 w-5 ml-2" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <p className="text-gray-500 text-sm">
            © 2024 SERM Platform. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
