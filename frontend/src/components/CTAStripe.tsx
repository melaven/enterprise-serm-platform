import { motion } from 'framer-motion'

function CTAStripe() {
  return (
    <section className="bg-[#0A0A0A] px-5 py-20 sm:px-8 lg:px-12">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.65, ease: 'easeOut' }}
        className="mx-auto max-w-5xl overflow-hidden rounded-[32px] border border-white/10 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.16),transparent_35%),linear-gradient(135deg,#0A0A0A_0%,#111827_48%,#0A0A0A_100%)] px-6 py-12 shadow-[0_30px_80px_rgba(0,0,0,0.35)] sm:px-10 lg:px-14"
      >
        <div className="flex flex-col items-center justify-between gap-8 text-center lg:flex-row lg:text-left">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-white/60">Начните сегодня</p>
            <h2 className="mt-4 text-[clamp(1.875rem,4vw,3rem)] font-black leading-[1.15] tracking-[-0.06em] text-white sm:text-4xl lg:text-5xl">
              Готовы закрыть негатив до того, как он повлияет на продажи?
            </h2>
          </div>

          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="button"
            className="inline-flex items-center justify-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow-[0_0_30px_rgba(255,255,255,0.2)] transition"
          >
            Получить аудит
          </motion.button>
        </div>
      </motion.div>
    </section>
  )
}

export default CTAStripe
