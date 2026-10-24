/**
 * Landing Page - Premium Dark Theme with Framer Motion Animations
 * Polished B2B design with smooth micro-interactions and scroll animations
 */

import { ArrowRight, Shield, Zap, BarChart3, Check, Users, Clock, TrendingUp } from 'lucide-react';
import { motion } from 'framer-motion';

// Animation variants
const fadeInUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0 },
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
      delayChildren: 0.1,
    },
  },
};

const cardHover = {
  y: -8,
  transition: { type: 'spring', stiffness: 300, damping: 20 },
};

const buttonSpring = {
  type: 'spring',
  stiffness: 400,
  damping: 25,
};

export function LandingPage() {
  return (
    <div className="relative min-h-screen bg-[#0B0C10]">
      {/* Subtle radial gradient background */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-gray-800/30 via-[#0B0C10] to-[#0B0C10] -z-10"></div>

      {/* Navigation */}
      <motion.nav
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="border-b border-gray-800 bg-[#0B0C10]/80 backdrop-blur-sm"
      >
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="h-8 w-8 text-[#C5FF4A]" />
              <span className="text-xl font-bold text-white">Tenable</span>
            </div>
            <div className="flex items-center gap-6">
              <a href="/login" className="text-sm font-medium text-gray-400 hover:text-white transition-colors">
                Sign In
              </a>
              <motion.a
                href="/register"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                transition={buttonSpring}
                className="rounded-md bg-[#C5FF4A] px-4 py-2 text-sm font-semibold text-black hover:bg-[#b0e63e] transition-colors"
              >
                Get Started
              </motion.a>
            </div>
          </div>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <section className="py-20 md:py-28">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="visible"
            className="text-center"
          >
            <motion.h1
              variants={fadeInUp}
              transition={{ type: 'spring', stiffness: 100, damping: 20 }}
              className="text-5xl md:text-7xl font-bold tracking-tight text-white"
            >
              Manage Your Online Reputation
              <span className="block mt-2 text-gray-300">
                With <span className="text-[#C5FF4A]">Intelligent</span> Insights
              </span>
            </motion.h1>
            
            <motion.p
              variants={fadeInUp}
              transition={{ type: 'spring', stiffness: 100, damping: 20 }}
              className="mx-auto mt-8 max-w-2xl text-lg md:text-xl leading-8 text-gray-400"
            >
              Aggregate reviews from multiple platforms, analyze sentiment automatically, 
              and respond to customers faster with intelligent recommendations.
            </motion.p>
            
            <motion.div
              variants={fadeInUp}
              transition={{ type: 'spring', stiffness: 100, damping: 20 }}
              className="mt-12 flex items-center justify-center gap-4"
            >
              <motion.a
                href="/register"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                transition={buttonSpring}
                className="flex items-center gap-2 rounded-md bg-[#C5FF4A] px-6 py-3.5 text-base font-semibold text-black hover:bg-[#b0e63e] transition-colors shadow-lg shadow-[#C5FF4A]/20"
              >
                Start Free Trial
                <ArrowRight className="h-5 w-5" />
              </motion.a>
              <motion.a
                href="#features"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                transition={buttonSpring}
                className="rounded-md border border-gray-700 bg-transparent px-6 py-3.5 text-base font-semibold text-gray-300 hover:bg-gray-800/50 transition-all"
              >
                Learn More
              </motion.a>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white">
              Everything You Need to Manage Reviews
            </h2>
            <p className="mt-4 text-lg text-gray-400">
              Powerful features designed for modern businesses
            </p>
          </motion.div>

          <div className="mt-16 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: BarChart3,
                title: 'Analytics Dashboard',
                description: 'Real-time insights into review sentiment, trends, and customer feedback across all platforms.',
              },
              {
                icon: Zap,
                title: 'Intelligent Analysis',
                description: 'Automatic sentiment detection and intelligent categorization of review content.',
              },
              {
                icon: Clock,
                title: '24/7 Monitoring',
                description: 'Continuous tracking of new reviews from Google Maps, Yandex, 2GIS, and more.',
              },
              {
                icon: Users,
                title: 'Team Collaboration',
                description: 'Assign reviews to team members and track response times with role-based access.',
              },
              {
                icon: TrendingUp,
                title: 'Trend Analysis',
                description: 'Identify patterns and emerging issues before they impact your reputation.',
              },
              {
                icon: Shield,
                title: 'Enterprise Security',
                description: 'Bank-level encryption and compliance with GDPR, SOC 2, and industry standards.',
              },
            ].map((feature, idx) => {
              const Icon = feature.icon;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-100px' }}
                  transition={{
                    type: 'spring',
                    stiffness: 100,
                    damping: 20,
                    delay: idx * 0.1,
                  }}
                  whileHover={cardHover}
                  className="rounded-lg border border-gray-800 bg-[#13151A] p-8 hover:border-gray-700 transition-colors cursor-pointer"
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-[#1a1d24]">
                    <Icon className="h-6 w-6 text-[#C5FF4A]" />
                  </div>
                  <h3 className="mt-6 text-lg font-semibold text-white">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-gray-400">{feature.description}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="bg-[#13151A]/50 py-20">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-white">
              Simple, Transparent Pricing
            </h2>
            <p className="mt-4 text-lg text-gray-400">
              Choose the plan that fits your business
            </p>
          </motion.div>

          <div className="mt-16 grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-12">
            {/* Free Plan */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ type: 'spring', stiffness: 100, damping: 20 }}
              whileHover={cardHover}
              className="rounded-lg border border-gray-800 bg-[#0B0C10] p-8 hover:border-gray-700 transition-colors"
            >
              <div className="mb-8">
                <h3 className="text-2xl font-bold text-white">Free</h3>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-5xl font-bold text-white tracking-tight">$0</span>
                  <span className="text-gray-400">/month</span>
                </div>
              </div>
              <ul className="space-y-3">
                {[
                  'Up to 100 reviews per month',
                  '50,000 analysis tokens',
                  'Basic analytics dashboard',
                  'Email support',
                  '5 platform integrations',
                ].map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-3">
                    <Check className="h-5 w-5 flex-shrink-0 text-[#C5FF4A]" />
                    <span className="text-sm text-gray-400">{feature}</span>
                  </li>
                ))}
              </ul>
              <motion.a
                href="/register"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                transition={buttonSpring}
                className="mt-8 block w-full rounded-md border border-gray-700 bg-transparent px-4 py-3 text-center text-sm font-semibold text-white hover:bg-gray-800/50 transition-all"
              >
                Get Started Free
              </motion.a>
            </motion.div>

            {/* Pro Plan */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ type: 'spring', stiffness: 100, damping: 20, delay: 0.1 }}
              whileHover={cardHover}
              className="relative rounded-lg border-2 border-[#C5FF4A] bg-[#0B0C10] p-8 shadow-lg shadow-[#C5FF4A]/10"
            >
              <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                <span className="rounded-full bg-[#C5FF4A] px-4 py-1 text-xs font-semibold uppercase tracking-wider text-black">
                  Most Popular
                </span>
              </div>
              <div className="mb-8">
                <h3 className="text-2xl font-bold text-white">Pro</h3>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="text-5xl font-bold text-white tracking-tight">$49</span>
                  <span className="text-gray-400">/month</span>
                </div>
              </div>
              <ul className="space-y-3">
                {[
                  '10,000 reviews per month',
                  '1,000,000 analysis tokens',
                  'Advanced analytics & reports',
                  'Priority 24/7 support',
                  'Unlimited platform integrations',
                  'CSV/Excel exports',
                  'API access',
                  'Custom integrations',
                ].map((feature, idx) => (
                  <li key={idx} className="flex items-start gap-3">
                    <Check className="h-5 w-5 flex-shrink-0 text-[#C5FF4A]" />
                    <span className="text-sm text-gray-400">{feature}</span>
                  </li>
                ))}
              </ul>
              <motion.a
                href="/register"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                transition={buttonSpring}
                className="mt-8 block w-full rounded-md bg-[#C5FF4A] px-4 py-3 text-center text-sm font-semibold text-black hover:bg-[#b0e63e] transition-colors shadow-lg shadow-[#C5FF4A]/20"
              >
                Start Free Trial
              </motion.a>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
            whileHover={{ y: -4 }}
            className="rounded-lg border border-gray-800 bg-[#13151A] px-8 py-16 text-center hover:border-gray-700 transition-colors"
          >
            <h2 className="text-3xl md:text-4xl font-bold text-white tracking-tight">
              Ready to Transform Your Review Management?
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-400">
              Join hundreds of businesses using Tenable to protect and enhance their online reputation.
            </p>
            <div className="mt-8">
              <motion.a
                href="/register"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                transition={buttonSpring}
                className="inline-flex items-center gap-2 rounded-md bg-[#C5FF4A] px-6 py-3.5 text-base font-semibold text-black hover:bg-[#b0e63e] transition-colors shadow-lg shadow-[#C5FF4A]/20"
              >
                Get Started Free
                <ArrowRight className="h-5 w-5" />
              </motion.a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 bg-[#0B0C10] py-12">
        <div className="mx-auto max-w-7xl px-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="h-6 w-6 text-[#C5FF4A]" />
              <span className="text-lg font-bold text-white">Tenable</span>
            </div>
            <p className="text-sm text-gray-400">
              © {new Date().getFullYear()} Tenable. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
