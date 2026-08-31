import { Check, Copy, Palette, Star } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

export type WidgetTheme = 'light' | 'dark'
export type WidgetLayout = 'slider' | 'grid' | 'badge' | 'bento'

export type WidgetConfig = {
  theme: WidgetTheme
  layout: WidgetLayout
  primary_color: string
  min_rating: number
  show_date: boolean
}

export type WidgetReview = {
  id: number
  author_name: string | null
  rating: number
  review_text: string
  created_at: string | null
}

const API_BASE_URL = 'http://localhost:8000'
const WIDGET_EMBED_BASE_URL = 'http://localhost:5174'

const defaultConfig: WidgetConfig = {
  theme: 'light',
  layout: 'slider',
  primary_color: '#4F46E5',
  min_rating: 4,
  show_date: true,
}

const layoutOptions: Array<{ value: WidgetLayout; label: string }> = [
  { value: 'slider', label: 'Slider' },
  { value: 'bento', label: 'Bento Grid' },
  { value: 'grid', label: 'Grid' },
  { value: 'badge', label: 'Badge' },
]

function useWidgetPreview() {
  const [config, setConfig] = useState<WidgetConfig>(defaultConfig)
  const [reviews, setReviews] = useState<WidgetReview[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadPreview = async () => {
      try {
        setLoading(true)
        const response = await fetch(`${API_BASE_URL}/api/v1/widgets/preview`, {
          headers: { Accept: 'application/json' },
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const payload = (await response.json()) as {
          config?: Partial<WidgetConfig>
          reviews?: WidgetReview[]
        }

        const nextConfig = { ...defaultConfig, ...(payload.config ?? {}) }
        setConfig(nextConfig)
        setReviews(payload.reviews ?? [])
        localStorage.setItem('widget-preview-reviews', JSON.stringify(payload.reviews ?? []))
      } catch (error) {
        console.error('Widget preview failed:', error)
      } finally {
        setLoading(false)
      }
    }

    void loadPreview()
  }, [])

  return { config, setConfig, reviews, loading }
}

export function WidgetBuilder() {
  const { config, setConfig, reviews } = useWidgetPreview()
  const [copied, setCopied] = useState(false)

  const iframePreviewUrl = useMemo(() => {
    const query = new URLSearchParams({
      theme: config.theme,
      layout: config.layout,
      accentColor: config.primary_color,
      minRating: String(config.min_rating),
      showDate: String(config.show_date),
    }).toString()

    return `${WIDGET_EMBED_BASE_URL}/widget-embed?${query}`
  }, [config])

  const embedCode = useMemo(() => {
    const scriptTag = `<script src="${API_BASE_URL}/api/v1/widgets/script.js" data-tenant-id="DEMO_TENANT" async></script>`
    const hostTag = `<div id="nexus-widget"></div>`
    return `<!-- Widget embed -->\n${scriptTag}\n${hostTag}`
  }, [])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(embedCode)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1400)
    } catch {
      setCopied(false)
    }
  }

  const themeClasses =
    config.theme === 'dark'
      ? 'bg-slate-900 text-slate-100 border-slate-700'
      : 'bg-slate-900 text-slate-100 border-slate-700'

  const themeButtonClass = (theme: WidgetTheme) => {
    if (config.theme === theme) {
      return 'bg-blue-600 text-white shadow-lg shadow-blue-500/30 ring-1 ring-blue-400/50'
    }

    return 'border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
  }

  const layoutButtonClass = (layout: WidgetLayout) => {
    if (config.layout === layout) {
      return 'bg-blue-600 text-white shadow-[0_0_0_1px_rgba(59,130,246,0.3)]'
    }

    return 'bg-slate-800 text-slate-300 hover:bg-slate-700'
  }

  const visibleReviews = reviews.filter((review) => review.rating >= config.min_rating)

  return (
    <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
      <aside className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-[0_16px_35px_rgba(15,23,42,0.35)] backdrop-blur-md">
        <div className="mb-5 flex items-center gap-2">
          <Palette className="h-5 w-5 text-blue-300" />
          <h2 className="text-lg font-semibold text-slate-100">Настройки виджета</h2>
        </div>

        <div className="space-y-5">
          <div>
            <p className="mb-2 text-sm font-medium text-slate-200">Тема</p>
            <div className="grid grid-cols-2 gap-2">
              {(['light', 'dark'] as WidgetTheme[]).map((theme) => (
                <button
                  key={theme}
                  type="button"
                  onClick={() => setConfig((current) => ({ ...current, theme }))}
                  className={`rounded-xl border px-3 py-2 text-sm font-medium transition ${themeButtonClass(theme)}`}
                >
                  {theme === 'light' ? 'Light' : 'Dark'}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-slate-200">Макет</p>
            <div className="grid gap-2">
              {layoutOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setConfig((current) => ({ ...current, layout: option.value }))}
                  className={`rounded-xl border px-3 py-2 text-left text-sm font-medium transition ${layoutButtonClass(option.value)}`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-200">
              Основной цвет
              <div className="mt-2 flex items-center gap-3">
                <input
                  type="color"
                  value={config.primary_color}
                  onChange={(event) =>
                    setConfig((current) => ({ ...current, primary_color: event.target.value }))
                  }
                  className="h-11 w-16 rounded-lg border border-slate-700 bg-slate-800 p-1"
                />
                <span className="text-sm text-slate-400">{config.primary_color}</span>
              </div>
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-200">
              Минимальный рейтинг
              <input
                type="range"
                min={1}
                max={5}
                value={config.min_rating}
                onChange={(event) =>
                  setConfig((current) => ({ ...current, min_rating: Number(event.target.value) }))
                }
                className="mt-2 w-full accent-blue-500"
              />
              <div className="mt-1 text-sm text-slate-400">{config.min_rating} ★ и выше</div>
            </label>
          </div>

          <label className="flex items-center justify-between rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-200">
            <span>Показывать дату</span>
            <input
              type="checkbox"
              checked={config.show_date}
              onChange={(event) =>
                setConfig((current) => ({ ...current, show_date: event.target.checked }))
              }
              className="h-4 w-4 accent-blue-500"
            />
          </label>
        </div>
      </aside>

      <div className="space-y-6">
        <div className={`rounded-2xl border p-5 shadow-flat ${themeClasses}`}>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-content-secondary">Review widget</p>
              <h3 className="mt-1 text-xl font-semibold">Что говорят клиенты</h3>
            </div>
            <div className="inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-medium" style={{ backgroundColor: `${config.primary_color}1A`, color: config.primary_color }}>
              <Star className="h-4 w-4 fill-current" />
              {visibleReviews.length} отзывов
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-slate-200/70 bg-slate-950/5">
            <iframe
              title="Widget preview"
              src={iframePreviewUrl}
              className="h-[420px] w-full border-0"
              loading="lazy"
            />
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-[0_16px_35px_rgba(15,23,42,0.35)] backdrop-blur-md">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold text-slate-100">Код для вставки</h3>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-blue-500 hover:bg-slate-700 hover:text-white"
            >
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Скопировано' : 'Скопировать'}
            </button>
          </div>

          <pre className="overflow-x-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100 ring-1 ring-slate-800">
            <code>{embedCode}</code>
          </pre>
        </div>
      </div>
    </div>
  )
}
