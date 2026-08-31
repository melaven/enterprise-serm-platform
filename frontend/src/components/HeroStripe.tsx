import { AnimatePresence, motion } from 'framer-motion'
import { BellRing, MessageSquareText, ShieldAlert, Sparkles, Star, TrendingUp, Zap } from 'lucide-react'
import { useState } from 'react'

const orbitItems = [
  { Icon: ShieldAlert, position: { left: '50%', top: '0%' } },
  { Icon: Star, position: { left: '100%', top: '25%' } },
  { Icon: TrendingUp, position: { left: '82%', top: '82%' } },
  { Icon: BellRing, position: { left: '18%', top: '82%' } },
  { Icon: Sparkles, position: { left: '0%', top: '25%' } },
  { Icon: Zap, position: { left: '50%', top: '100%' } },
]

function HeroStripe() {
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      setError('Введите email, чтобы получить аудит.')
      setSuccess(false)
      return
    }

    try {
      setIsSubmitting(true)
      setError('')

      const response = await fetch('http://127.0.0.1:3000/api/lead', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: trimmedEmail }),
      })

      if (!response.ok) {
        throw new Error('Lead request failed')
      }

      setSuccess(true)
      setEmail('')
    } catch {
      setSuccess(false)
      setError('Не удалось отправить заявку. Попробуйте позже.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-[#0A0A0A] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.12),rgba(255,255,255,0.04)_18%,rgba(10,10,10,0)_42%,rgba(10,10,10,0.78)_100%)]" aria-hidden="true" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(164,164,164,0.18),transparent_32%)]" aria-hidden="true" />

      <section className="relative mx-auto flex min-h-screen max-w-7xl items-center px-5 py-16 sm:px-8 lg:px-12">
        <div className="grid w-full items-center gap-10 lg:grid-cols-[1.2fr_0.8fr]">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
            className="flex flex-col items-center justify-center text-center lg:items-start lg:text-left"
          >
            <div className="relative flex h-[420px] w-[420px] items-center justify-center sm:h-[500px] sm:w-[500px]">
              <motion.div
                className="absolute inset-6"
                animate={{ rotate: 360 }}
                transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}
                aria-hidden="true"
              >
                {orbitItems.map(({ Icon, position }, index) => (
                  <motion.div
                    key={`${Icon.name}-${index}`}
                    className="absolute"
                    style={{
                      left: position.left,
                      top: position.top,
                      transform: 'translate(-50%, -50%)',
                    }}
                    animate={{ rotate: -360 }}
                    transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}
                  >
                    <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/20 bg-white/5 shadow-[0_0_24px_rgba(255,255,255,0.06)] backdrop-blur-sm sm:h-16 sm:w-16">
                      <Icon className="h-5 w-5 text-white sm:h-6 sm:w-6" />
                    </div>
                  </motion.div>
                ))}
              </motion.div>

              <motion.div
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.7, delay: 0.15 }}
                className="relative z-10 w-full max-w-none"
              >
                <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[10px] font-medium uppercase tracking-[0.2em] text-white/75 backdrop-blur-sm sm:text-[11px]">
                  <MessageSquareText className="h-3.5 w-3.5" />
                  Reputation Defense
                </div>

                <h1 className="mt-6 w-full font-['Inter',sans-serif] text-[clamp(2rem,5vw,4.3rem)] font-black leading-[1.1] tracking-[-0.06em] text-transparent bg-gradient-to-b from-white to-neutral-400 bg-clip-text">
                  Теряете клиентов из-за негатива в сети?
                </h1>
              </motion.div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 28 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 0.1, ease: 'easeOut' }}
            className="flex justify-center lg:justify-end"
          >
            <div className="w-full max-w-md rounded-2xl border border-white/20 bg-white/10 p-5 shadow-[0_0_45px_rgba(255,255,255,0.08)] backdrop-blur-md sm:p-7">
              <div className="mb-5 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15">
                  <ShieldAlert className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white/80">Проверка репутации</p>
                  <p className="text-xs uppercase tracking-[0.18em] text-white/50">AI monitor</p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-white/80">Email</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-white/20 bg-white/5 px-4 py-3 text-sm text-white placeholder:text-white/40 focus:border-white/40 focus:outline-none focus:ring-2 focus:ring-white/20"
                    aria-label="Email"
                  />
                </label>

                <motion.button
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                  type="submit"
                  disabled={isSubmitting}
                  className="flex w-full items-center justify-center rounded-xl bg-white px-4 py-3 text-sm font-semibold text-[#0A0A0A] shadow-[0_0_30px_rgba(255,255,255,0.25)] transition disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isSubmitting ? 'Отправка...' : 'Получить аудит'}
                </motion.button>
              </form>

              <AnimatePresence>
                {success && (
                  <motion.div
                    initial={{ opacity: 0, y: 8, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -8, scale: 0.98 }}
                    transition={{ duration: 0.25, ease: 'easeOut' }}
                    className="mt-4 rounded-xl border border-emerald-400/40 bg-emerald-500/15 px-3 py-2 text-sm font-medium text-emerald-100 shadow-[0_0_18px_rgba(52,211,153,0.28)]"
                  >
                    Уведомление отправлено в Telegram
                  </motion.div>
                )}
              </AnimatePresence>

              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    className="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-100"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </section>
    </main>
  )
}

export default HeroStripe
