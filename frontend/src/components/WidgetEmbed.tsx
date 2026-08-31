import { ChevronLeft, ChevronRight, Star } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

type WidgetTheme = 'light' | 'dark'
type WidgetLayout = 'slider' | 'grid' | 'badge' | 'bento'

type EmbeddedReview = {
  id: number
  author_name: string | null
  rating: number
  review_text: string
  created_at: string | null
}

const API_BASE_URL = 'http://localhost:8000'

const fallbackReviews: EmbeddedReview[] = [
  {
    id: 101,
    author_name: 'Алексей',
    rating: 5,
    review_text:
      'Площадка очень удобная, всё быстро и прозрачно. Заказы обрабатываются без задержек, а поддержка всегда помогает в спорных моментах.',
    created_at: '2024-08-12T10:00:00.000Z',
  },
  {
    id: 102,
    author_name: 'Мария',
    rating: 5,
    review_text:
      'Очень понравился интерфейс и скорость обслуживания. Мы быстро получили результаты, и команда отлично объяснила, что именно улучшили.',
    created_at: '2024-08-14T09:30:00.000Z',
  },
  {
    id: 103,
    author_name: 'Дмитрий',
    rating: 4,
    review_text:
      'Надёжный сервис с понятной логикой. Система помогает улучшать видимость в локальном поиске и экономит массу времени на рутине.',
    created_at: '2024-08-17T14:15:00.000Z',
  },
]

const sourceBadges = [
  { label: 'Яндекс', tone: 'bg-yellow-300/20 text-yellow-200 border-yellow-300/30' },
  { label: '2ГИС', tone: 'bg-emerald-400/20 text-emerald-200 border-emerald-300/30' },
  { label: 'Google', tone: 'bg-blue-400/20 text-blue-200 border-blue-300/30' },
]

function parseQueryParam(name: string): string {
  if (typeof window === 'undefined') return ''
  const params = new URLSearchParams(window.location.search)
  return params.get(name) ?? ''
}

export function WidgetEmbed() {
  const fallbackTheme: WidgetTheme = 'light'
  const rawTheme = parseQueryParam('theme')
  const theme: WidgetTheme = rawTheme === 'dark' || rawTheme === 'light' ? rawTheme : fallbackTheme

  const layout = (parseQueryParam('layout') || 'slider') as WidgetLayout
  const primaryColor = parseQueryParam('accentColor') || parseQueryParam('primaryColor') || '#4F46E5'
  const minRating = Number(parseQueryParam('minRating') || 4)
  const showDate = parseQueryParam('showDate') !== 'false'

  const [reviews, setReviews] = useState<EmbeddedReview[]>(fallbackReviews)
  const [loading, setLoading] = useState(true)
  const [activeSlide, setActiveSlide] = useState(0)

  useEffect(() => {
    const loadReviews = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/widgets/preview`, {
          headers: { Accept: 'application/json' },
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const payload = (await response.json()) as { reviews?: EmbeddedReview[] }
        const nextReviews = (payload.reviews ?? []).map((review, index) => ({
          ...review,
          id: review.id ?? index + 200,
        }))

        setReviews(nextReviews.length > 0 ? nextReviews : fallbackReviews)
        localStorage.setItem('widget-preview-reviews', JSON.stringify(nextReviews.length > 0 ? nextReviews : fallbackReviews))
      } catch {
        const raw = localStorage.getItem('widget-preview-reviews')

        if (!raw) {
          setReviews(fallbackReviews)
          return
        }

        try {
          const parsed = JSON.parse(raw) as EmbeddedReview[]
          setReviews(parsed.length > 0 ? parsed : fallbackReviews)
        } catch {
          setReviews(fallbackReviews)
        }
      } finally {
        setLoading(false)
      }
    }

    void loadReviews()
  }, [])

  const dedupedReviews = useMemo(() => {
    const uniqueReviews = Array.from(new Map((reviews ?? fallbackReviews).map((review) => [String(review.id), review])).values())
    return uniqueReviews
  }, [reviews])

  const filteredReviews = useMemo(
    () => dedupedReviews.filter((review) => review.rating >= minRating),
    [dedupedReviews, minRating],
  )

  const visibleReviews = filteredReviews.length > 0 ? filteredReviews.slice(0, layout === 'badge' ? 4 : layout === 'bento' ? 4 : 3) : []
  const isDark = theme === 'dark'

  useEffect(() => {
    if (layout === 'slider' && visibleReviews.length > 0) {
      setActiveSlide((current) => (current >= visibleReviews.length ? 0 : current))
    }
  }, [layout, visibleReviews.length])

  const currentReview = layout === 'slider' && visibleReviews.length > 0 ? visibleReviews[activeSlide % visibleReviews.length] : null

  const shellClasses = isDark
    ? 'min-h-screen bg-[radial-gradient(circle_at_top,_rgba(79,70,229,0.28),_transparent_38%),linear-gradient(135deg,#020617_0%,#0f172a_45%,#111827_100%)] p-4 text-slate-50'
    : 'min-h-screen bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.12),_transparent_38%),linear-gradient(135deg,#f8fafc_0%,#eef2ff_38%,#f8fafc_100%)] p-4 text-slate-900'

  const containerClasses = isDark
    ? 'mx-auto max-w-[560px] rounded-[28px] border border-white/10 bg-slate-900/70 p-4 shadow-[0_24px_80px_rgba(15,23,42,0.6)] backdrop-blur-xl'
    : 'mx-auto max-w-[560px] rounded-[28px] border border-white/60 bg-white/70 p-4 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl'

  const cardClasses = isDark
    ? 'rounded-[22px] border border-slate-700/80 bg-slate-800/70 text-slate-100'
    : 'rounded-[22px] border border-slate-200/80 bg-white/70 text-slate-900'

  const renderReviewCard = (review: EmbeddedReview, featured = false) => (
    <div
      key={review.id}
      className={`${cardClasses} p-4 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_18px_35px_rgba(79,70,229,0.18)] ${featured ? 'md:col-span-2 md:row-span-2' : ''}`}
      style={{
        boxShadow: isDark ? '0 10px 30px rgba(15, 23, 42, 0.4)' : '0 10px 30px rgba(15, 23, 42, 0.08)',
      }}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold">{review.author_name || 'Аноним'}</div>
          {showDate ? (
            <div className={`mt-1 text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              {new Date(review.created_at ?? Date.now()).toLocaleDateString('ru-RU')}
            </div>
          ) : null}
        </div>

        <div
          className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-bold"
          style={{ backgroundColor: `${primaryColor}1A`, color: primaryColor }}
        >
          <Star className="h-3.5 w-3.5 fill-current" />
          {review.rating}
        </div>
      </div>

      <p
        className={`${featured ? 'text-base leading-7' : 'text-sm leading-6'} ${isDark ? 'text-slate-200' : 'text-slate-700'}`}
      >
        “{review.review_text}”
      </p>
    </div>
  )

  return (
    <div className={shellClasses}>
      <div className={containerClasses}>
        <div className="mb-4 rounded-[24px] border border-white/20 bg-gradient-to-r from-indigo-500/15 via-violet-500/10 to-cyan-400/10 p-4 backdrop-blur-md">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-300 to-orange-400 text-base font-bold text-slate-900 shadow-lg shadow-amber-500/20">
                ★
              </div>
              <div>
                <div className="text-2xl font-black leading-none text-indigo-300">4.9</div>
                <div className="mt-1 text-[10px] uppercase tracking-[0.25em] text-slate-400">Средний рейтинг</div>
              </div>
            </div>

            <div className="text-right">
              <div className="text-base font-bold text-slate-100">120+</div>
              <div className="text-[10px] uppercase tracking-[0.25em] text-slate-400">отзывов</div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2 border-t border-white/10 pt-3">
            <span className="text-[10px] uppercase tracking-[0.25em] text-slate-400">Источники</span>
            <div className="flex items-center gap-2">
              {sourceBadges.map((badge) => (
                <span
                  key={badge.label}
                  className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${badge.tone}`}
                >
                  {badge.label}
                </span>
              ))}
            </div>
          </div>
        </div>

        {loading ? (
          <div className={`rounded-[20px] border border-dashed p-5 text-sm ${isDark ? 'border-slate-700 text-slate-300' : 'border-slate-300 text-slate-600'}`}>
            Загрузка отзывов...
          </div>
        ) : visibleReviews.length === 0 ? (
          <div className={`rounded-[20px] border border-dashed p-5 text-sm ${isDark ? 'border-slate-700 text-slate-300' : 'border-slate-300 text-slate-600'}`}>
            Нет отзывов по выбранному фильтру.
          </div>
        ) : layout === 'slider' ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <button
                type="button"
                aria-label="Предыдущий отзыв"
                onClick={() => setActiveSlide((current) => (current === 0 ? visibleReviews.length - 1 : current - 1))}
                className={`flex h-10 w-10 items-center justify-center rounded-full border transition hover:scale-105 ${isDark ? 'border-slate-700 bg-slate-800/80 text-slate-100 hover:border-indigo-400' : 'border-slate-200 bg-white/80 text-slate-700 hover:border-indigo-300'}`}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>

              <div className="flex items-center gap-2">
                {visibleReviews.map((review, index) => (
                  <button
                    key={review.id}
                    type="button"
                    aria-label={`Показать отзыв ${index + 1}`}
                    onClick={() => setActiveSlide(index)}
                    className={`h-2.5 rounded-full transition-all ${index === activeSlide ? 'w-8 bg-indigo-500' : 'w-2.5 bg-slate-400/60'}`}
                  />
                ))}
              </div>

              <button
                type="button"
                aria-label="Следующий отзыв"
                onClick={() => setActiveSlide((current) => (current + 1) % visibleReviews.length)}
                className={`flex h-10 w-10 items-center justify-center rounded-full border transition hover:scale-105 ${isDark ? 'border-slate-700 bg-slate-800/80 text-slate-100 hover:border-indigo-400' : 'border-slate-200 bg-white/80 text-slate-700 hover:border-indigo-300'}`}
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            {currentReview ? renderReviewCard(currentReview, true) : null}
          </div>
        ) : layout === 'bento' ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {visibleReviews.map((review, index) =>
              renderReviewCard(review, index === 0),
            )}
          </div>
        ) : (
          <div
            className={
              layout === 'grid'
                ? 'grid gap-3 md:grid-cols-2'
                : 'flex flex-wrap gap-3'
            }
          >
            {visibleReviews.map((review) => (
              <div
                key={review.id}
                className={`${cardClasses} p-4 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_18px_35px_rgba(79,70,229,0.18)] ${layout === 'badge' ? 'min-w-[170px] flex-1' : ''}`}
                style={{
                  boxShadow: isDark ? '0 10px 30px rgba(15, 23, 42, 0.4)' : '0 10px 30px rgba(15, 23, 42, 0.08)',
                }}
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold">{review.author_name || 'Аноним'}</div>
                    {showDate ? (
                      <div className={`mt-1 text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {new Date(review.created_at ?? Date.now()).toLocaleDateString('ru-RU')}
                      </div>
                    ) : null}
                  </div>

                  <div
                    className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-bold"
                    style={{ backgroundColor: `${primaryColor}1A`, color: primaryColor }}
                  >
                    <Star className="h-3.5 w-3.5 fill-current" />
                    {review.rating}
                  </div>
                </div>

                <p className={`text-sm leading-6 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                  “{review.review_text}”
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
