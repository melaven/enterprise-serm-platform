export type ReviewPlatform = 'Яндекс' | 'Google' | '2ГИС'

export interface Review {
  id: number
  company_id: number
  platform_id: number
  external_review_id: string
  author_name: string | null
  rating: number
  review_text: string
  sentiment: string | null
  processing_status: string | null
  created_at: string | null
}

export interface ReviewStats {
  total: number
  averageRating: number
  syncRate: number
  positiveRatio: number
}

const API_BASE_URL = 'http://localhost:8000'
const API_REVIEWS_URL = `${API_BASE_URL}/api/v1/reviews`

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

const platformMap: Record<number, ReviewPlatform> = {
  1: 'Яндекс',
  2: 'Google',
  3: '2ГИС',
}

export function getPlatformLabel(platformId: number): ReviewPlatform {
  return platformMap[platformId] ?? 'Яндекс'
}

function normalizeReview(value: unknown): Review {
  if (!isRecord(value)) {
    throw new Error('Некорректный формат записи отзыва.')
  }

  const id = Number(value.id ?? 0)
  const companyId = Number(value.company_id ?? 0)
  const platformId = Number(value.platform_id ?? 1)
  const rating = Number(value.rating ?? 0)

  if (!value.external_review_id || !value.review_text) {
    throw new Error('Отзыв не содержит обязательных полей.')
  }

  return {
    id,
    company_id: companyId,
    platform_id: platformId,
    external_review_id: String(value.external_review_id),
    author_name: value.author_name === null || value.author_name === undefined ? null : String(value.author_name),
    rating,
    review_text: String(value.review_text),
    sentiment: value.sentiment === null || value.sentiment === undefined ? null : String(value.sentiment),
    processing_status:
      value.processing_status === null || value.processing_status === undefined
        ? null
        : String(value.processing_status),
    created_at: value.created_at === null || value.created_at === undefined ? null : String(value.created_at),
  }
}

export async function fetchReviews(): Promise<Review[]> {
  try {
    const response = await fetch(API_REVIEWS_URL, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      cache: 'no-store',
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    const payload: unknown = await response.json()

    if (!Array.isArray(payload)) {
      throw new Error('Некорректный ответ API: ожидался массив отзывов.')
    }

    return payload.map(normalizeReview)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Неизвестная ошибка загрузки отзывов.'
    throw new Error(`Не удалось загрузить отзывы: ${message}`)
  }
}

export function calculateReviewStats(reviews: Review[]): ReviewStats {
  const total = reviews.length

  if (total === 0) {
    return {
      total: 0,
      averageRating: 0,
      syncRate: 0,
      positiveRatio: 0,
    }
  }

  const averageRating = Number(
    (reviews.reduce((sum, review) => sum + review.rating, 0) / total).toFixed(1),
  )

  const positiveRatio = Math.round(
    (reviews.filter((review) => review.rating >= 4).length / total) * 100,
  )

  const syncRate = 100

  return {
    total,
    averageRating,
    syncRate,
    positiveRatio,
  }
}

export async function fetchReviewStats(): Promise<ReviewStats> {
  const comments = await fetchReviews()
  return calculateReviewStats(comments)
}
