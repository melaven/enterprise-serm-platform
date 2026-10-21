/**
 * Landing page for review metrics and Sentiment Intelligence.
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
      'До 5 импортов из разрешённых источников',
      '100 отзывов в месяц',
      '50 000 токенов для SI-анализа',
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
      'Расширенные возможности импорта',
      '10,000 отзывов в месяц',
      '1 000 000 токенов для SI-анализа',
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
        'relative flex flex-col rounded-sm border p-6 transition-colors duration-200',
        tier.recommended
          ? 'border-plum bg-plum text-white'
          : 'border-chrome-600 bg-ink-900 hover:border-chrome-400'
      )}
    >
      {/* Recommended Badge */}
      {tier.recommended && (
        <div
          className="absolute -top-3 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-sm bg-lime px-3 py-1 text-xs font-semibold uppercase tracking-wider text-ink-950"
        >
          <Crown className="h-3 w-3" />
          Recommended
        </div>
      )}

      {/* Header */}
      <div className="mb-6">
        <h3 className="mb-2 text-lg font-semibold text-white">{tier.name}</h3>
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold text-white">${tier.price}</span>
          <span className="text-chrome-300">/{tier.interval}</span>
        </div>
      </div>

      {/* Features */}
      <ul className="mb-8 flex-1 space-y-3">
        {tier.features.map((feature, index) => (
          <li key={index} className="flex items-start gap-2 text-sm">
            <Check
              className="mt-0.5 h-4 w-4 shrink-0 text-plum-200"
            />
            <span className={tier.recommended ? 'text-white/90' : 'text-chrome-300'}>{feature}</span>
          </li>
        ))}
      </ul>

      {/* CTA Button */}
      <Link to="/register">
        <Button
          className="w-full"
          variant={tier.recommended ? 'accent' : 'outline'}
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
    <div className="rounded-sm border border-plum-800 bg-ink-900 p-6 transition-colors hover:border-plum-500">
      <div className="mb-4 text-plum-200">
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
    <div className="min-h-screen bg-ink text-chrome-300">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 border-b border-chrome-600 bg-ink-900">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <span className="text-xl font-bold text-white">SERM</span>
            </div>
            <div className="flex items-center gap-4">
              <Link to="/login">
                <Button variant="ghost" className="text-chrome-300 hover:text-white">
                  Login
                </Button>
              </Link>
              <Link to="/register">
                <Button variant="accent">
                  Get Started
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="px-4 py-24 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <h1
            className="mb-6 text-4xl font-bold text-white"
            style={{ lineHeight: 1.2 }}
          >
            Review Metrics &{' '}
            <span className="bg-plum px-2 text-white">Sentiment Intelligence</span>
          </h1>
          <p className="mx-auto mb-8 max-w-3xl text-xl text-chrome-300">
            Аналитика динамики оценок, тональности и категорий проблем. SI-Ассистент
            готовит черновики ответов для ручной публикации; исходные тексты не сохраняются.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link to="/register">
              <Button size="lg" variant="accent" className="px-6 text-base">
                Start Free Trial
                <ArrowRight className="h-5 w-5 ml-2" />
              </Button>
            </Link>
            <Link to="/pricing">
              <Button
                size="lg"
                variant="outline"
                className="border-chrome-600 px-6 text-base text-white hover:bg-ink-50"
              >
                View Pricing
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="bg-plum px-4 py-24 text-white sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-white mb-4">
              A clearer view of service quality
            </h2>
            <p className="mx-auto max-w-2xl text-white/75">
              Review trends, sentiment and service issues in one analytical workspace.
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
              title="Sentiment Intelligence"
              description="Тональность и категории проблем на основе локального анализа без хранения исходного текста."
            />
            <FeatureCard
              icon={<Shield className="h-8 w-8" />}
              title="SI-Ассистент"
              description="Подготавливает черновик ответа; отправку на площадке подтверждает и выполняет человек."
            />
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="px-4 py-24 sm:px-6 lg:px-8">
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
      <section className="bg-plum px-4 py-24 text-white sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Turn review trends into better service
          </h2>
          <p className="mb-8 text-white/75">
            Следите за динамикой оценок и превращайте обратную связь в измеримые улучшения сервиса.
          </p>
          <Link to="/register">
            <Button size="lg" variant="accent" className="px-8 text-lg">
              Get Started Now
              <ArrowRight className="h-5 w-5 ml-2" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-chrome-600 px-4 py-12 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <p className="text-gray-500 text-sm">
            © 2026 Tenable SERM
          </p>
        </div>
      </footer>
    </div>
  );
}
