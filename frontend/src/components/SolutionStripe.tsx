import { motion, useInView } from 'framer-motion'
import { BellRing, Check, ShieldCheck } from 'lucide-react'
import { useRef } from 'react'

const cards = [
  {
    icon: BellRing,
    iconClass: 'bg-[#f9e7ee] text-[#d9485f]',
    title: '🚨 Негативный отзыв перехвачен на Яндекс Картах',
    status: 'Заблокировано',
    statusClass: 'bg-[#fef2f2] text-[#b91c1c]',
  },
  {
    icon: ShieldCheck,
    iconClass: 'bg-[#ecfdf5] text-[#059669]',
    title: '🛡️ Репутационный аудит завершен',
    status: '100% Защита',
    statusClass: 'bg-[#ecfdf5] text-[#047857]',
  },
  {
    icon: Check,
    iconClass: 'bg-[#eef2ff] text-[#4f46e5]',
    title: '✨ Новая заявка отправлена в CRM',
    status: 'Успешно',
    statusClass: 'bg-[#eef2ff] text-[#4338ca]',
  },
]

function SolutionStripe() {
  const ref = useRef<HTMLElement | null>(null)
  const isInView = useInView(ref, { once: true, amount: 0.35 })

  return (
    <section
      ref={ref}
      className="relative isolate overflow-hidden bg-[#F8F9FB] px-5 py-20 text-slate-900 sm:px-8 lg:px-12"
    >
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-[-8%] top-[-10%] h-72 w-72 rounded-full bg-purple-300/30 blur-3xl" />
        <div className="absolute right-[-5%] top-[12%] h-96 w-96 rounded-full bg-indigo-300/30 blur-3xl" />
        <div className="absolute bottom-[-10%] left-[35%] h-80 w-80 rounded-full bg-pink-200/50 blur-3xl" />
      </div>

      <div className="mx-auto max-w-6xl">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 18 }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className="mx-auto max-w-3xl text-center"
        >
          <h2 className="font-sans text-[clamp(1.875rem,4vw,3rem)] font-black leading-[1.15] tracking-[-0.06em] text-slate-900 sm:text-4xl lg:text-5xl">
            Все уведомления и аналитика — в одном месте
          </h2>
        </motion.div>

        <div className="relative mx-auto mt-12 flex max-w-5xl items-center justify-center">
          {cards.map(({ icon: Icon, iconClass, title, status, statusClass }, index) => (
            <motion.article
              key={title}
              initial={{ opacity: 0, x: index === 0 ? -40 : index === 1 ? 0 : 40, y: 30, rotate: index === 0 ? -12 : index === 1 ? 0 : 12, scale: 0.96 }}
              animate={isInView ? { opacity: 1, x: 0, y: 0, rotate: 0, scale: 1 } : { opacity: 0, x: index === 0 ? -40 : index === 1 ? 0 : 40, y: 30, rotate: index === 0 ? -12 : index === 1 ? 0 : 12, scale: 0.96 }}
              transition={{ duration: 0.7, delay: index * 0.2, ease: 'easeOut' }}
              className={`absolute w-[min(88vw,360px)] rounded-2xl border border-slate-100/80 bg-white/90 p-4 shadow-xl backdrop-blur-sm ${
                index === 0 ? 'left-0 top-8 z-10 sm:left-8 lg:left-12' :
                index === 1 ? 'top-0 z-20 sm:top-0' :
                'right-0 top-8 z-10 sm:right-8 lg:right-12'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${iconClass}`}>
                  <Icon className="h-5 w-5" />
                </div>
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass}`}>
                  {status}
                </span>
              </div>

              <p className="mt-4 text-sm font-medium leading-6 text-slate-800">{title}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}

export default SolutionStripe
