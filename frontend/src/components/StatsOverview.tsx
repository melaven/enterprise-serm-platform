import { BarChart3, RefreshCcw, Star } from 'lucide-react'

import type { ReviewStats } from '../api/reviews'

type StatsOverviewProps = {
  stats: ReviewStats
}

const cards = [
  {
    label: 'Всего отзывов',
    valueKey: 'total',
    icon: BarChart3,
    accent: 'text-slate-100',
  },
  {
    label: 'Средняя оценка',
    valueKey: 'averageRating',
    icon: Star,
    accent: 'text-blue-300',
  },
  {
    label: '% синхронизации',
    valueKey: 'syncRate',
    icon: RefreshCcw,
    accent: 'text-violet-300',
  },
] as const

export function StatsOverview({ stats }: StatsOverviewProps) {
  return (
    <section className="grid gap-4 md:grid-cols-3">
      {cards.map(({ label, valueKey, icon: Icon, accent }) => {
        const value = stats[valueKey]
        const formattedValue =
          valueKey === 'total'
            ? String(value)
            : valueKey === 'averageRating'
              ? value.toFixed(1)
              : `${value}%`

        return (
          <div
            key={label}
            className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-[0_16px_35px_rgba(15,23,42,0.35)] backdrop-blur-md"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">{label}</p>
                <h2 className={`mt-3 text-3xl font-semibold ${accent}`}>{formattedValue}</h2>
              </div>

              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-800 text-slate-100 ring-1 ring-slate-700">
                <Icon className="h-5 w-5" />
              </div>
            </div>
          </div>
        )
      })}
    </section>
  )
}
