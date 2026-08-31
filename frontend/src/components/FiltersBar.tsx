import { Search } from 'lucide-react'

import type { ReviewPlatform } from '../api/reviews'

type PlatformFilter = 'all' | ReviewPlatform

type FiltersBarProps = {
  search: string
  platform: PlatformFilter
  rating: string
  onSearchChange: (value: string) => void
  onPlatformChange: (value: PlatformFilter) => void
  onRatingChange: (value: string) => void
}

const platformOptions: Array<{ label: string; value: PlatformFilter }> = [
  { label: 'Все', value: 'all' },
  { label: 'Яндекс', value: 'Яндекс' },
  { label: 'Google', value: 'Google' },
  { label: '2ГИС', value: '2ГИС' },
]

const ratingOptions = [
  { label: 'Все оценки', value: 'all' },
  { label: '5 stars', value: '5' },
  { label: '4 stars', value: '4' },
  { label: '3 stars', value: '3' },
  { label: '2 stars', value: '2' },
  { label: '1 star', value: '1' },
]

export function FiltersBar({
  search,
  platform,
  rating,
  onSearchChange,
  onPlatformChange,
  onRatingChange,
}: FiltersBarProps) {
  return (
    <section className="mt-8 rounded-2xl border border-slate-800 bg-slate-900/80 p-4 shadow-[0_16px_35px_rgba(15,23,42,0.35)] backdrop-blur-md">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <label className="relative block w-full lg:max-w-md">
          <span className="sr-only">Поиск по отзыву или автору</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Поиск по отзыву или автору"
            className="w-full rounded-xl border border-slate-700 bg-slate-800 py-2.5 pl-10 pr-3 text-sm text-white placeholder:text-slate-400 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
          />
        </label>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <span>Платформа</span>
            <select
              value={platform}
              onChange={(event) => onPlatformChange(event.target.value as PlatformFilter)}
              className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            >
              {platformOptions.map((option) => (
                <option key={option.value} value={option.value} className="bg-slate-800 text-white">
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-sm text-slate-300">
            <span>Оценка</span>
            <select
              value={rating}
              onChange={(event) => onRatingChange(event.target.value)}
              className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            >
              {ratingOptions.map((option) => (
                <option key={option.value} value={option.value} className="bg-slate-800 text-white">
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
    </section>
  )
}
