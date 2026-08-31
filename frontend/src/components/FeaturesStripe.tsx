import { motion, useInView } from 'framer-motion'
import { BellRing, Bot, ShieldCheck } from 'lucide-react'
import { useRef } from 'react'

const features = [
  {
    icon: BellRing,
    title: 'Уведомления в реальном времени',
    text: 'Мы ловим негативные упоминания в момент появления и оперативно направляем сигнал в ваши каналы.',
    accent: 'from-rose-100 to-rose-50',
  },
  {
    icon: ShieldCheck,
    title: 'Автоматическая защита репутации',
    text: 'Система формирует ответные действия, блокирует негатив и помогает сохранить доверие клиентов.',
    accent: 'from-emerald-100 to-emerald-50',
  },
  {
    icon: Bot,
    title: 'ИИ-аналитика и CRM-стек',
    text: 'Все данные, заявки и статусы собираются в одном месте, чтобы команды принимали решения быстрее.',
    accent: 'from-indigo-100 to-indigo-50',
  },
]

function FeaturesStripe() {
  const ref = useRef<HTMLElement | null>(null)
  const isInView = useInView(ref, { once: true, amount: 0.3 })

  return (
    <section ref={ref} className="bg-[#F8F9FB] px-5 py-20 sm:px-8 lg:px-12">
      <div className="mx-auto max-w-6xl">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="mx-auto max-w-2xl text-center"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Преимущества</p>
          <h2 className="mt-4 text-2xl sm:text-3xl md:text-4xl font-bold max-w-2xl mx-auto leading-tight text-slate-900">
            Бизнес получает контроль над репутацией без лишней рутины
          </h2>
        </motion.div>

        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {features.map(({ icon: Icon, title, text, accent }, index) => (
            <motion.article
              key={title}
              initial={{ opacity: 0, y: 28, scale: 0.96 }}
              animate={isInView ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 28, scale: 0.96 }}
              transition={{ duration: 0.6, delay: index * 0.2, ease: 'easeOut' }}
              className="rounded-3xl border border-slate-200/80 bg-white p-6 shadow-[0_20px_50px_rgba(15,23,42,0.06)]"
            >
              <div className={`flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br ${accent}`}>
                <Icon className="h-5 w-5 text-slate-900" />
              </div>
              <h3 className="mt-5 text-xl font-bold tracking-[-0.04em] text-slate-900">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-600">{text}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}

export default FeaturesStripe
