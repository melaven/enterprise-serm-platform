/**
 * Контракт апрува антикризисного черновика. Без зависимостей от DOM/axios:
 * тестируется в Node (см. approveDraftLogic.test.ts).
 *
 * POST /api/v1/reviews/{review_id}/drafts/{draft_id}/approve  { edited_text }
 *   200 { draft, idempotent, publication_status: "outbox_pending" }
 *   409 { detail }  другой менеджер уже подтвердил иной черновик
 *   403                                роль без прав (нужен owner/admin)
 *   400/422                            пустой текст / ошибка валидации
 *   5xx / сеть                         ответ не отправлен
 */

export type UserRole = 'owner' | 'admin' | 'member';

/** Публиковать ответы категории CRITICAL_RISK могут только owner и admin. */
export function canPublishCritical(role: UserRole): boolean {
  return role === 'owner' || role === 'admin';
}

export interface ApproveRequest {
  readonly reviewId: string;
  readonly draftId: string;
  readonly content: string;
}

export interface ApproveResult {
  readonly approved_draft_id: string;
  readonly status: 'approved';
  readonly outbox_queued: boolean;
}

export type ApproveErrorKind = 'conflict' | 'forbidden' | 'validation' | 'network' | 'server';

export class ApproveError extends Error {
  readonly kind: ApproveErrorKind;
  /** Только для conflict: черновик, который уже подтвердил другой менеджер. */
  readonly approvedDraftId: string | null;

  constructor(kind: ApproveErrorKind, message: string, approvedDraftId: string | null = null) {
    super(message);
    this.name = 'ApproveError';
    this.kind = kind;
    this.approvedDraftId = approvedDraftId;
  }
}

export const approveEndpoint = (reviewId: string, draftId: string): string =>
  `/v1/reviews/${encodeURIComponent(reviewId)}/drafts/${encodeURIComponent(draftId)}/approve`;

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null;
}

/** Превращает HTTP-ответ в ApproveResult либо бросает типизированный ApproveError. */
export function interpretApproveResponse(status: number, body: unknown): ApproveResult {
  const data = asRecord(body);

  if (status === 200) {
    const draft = data === null ? null : asRecord(data.draft);
    if (
      draft !== null &&
      typeof draft.id === 'string' &&
      draft.id !== '' &&
      draft.is_approved === true &&
      data?.idempotent !== undefined &&
      typeof data.idempotent === 'boolean' &&
      data.publication_status === 'outbox_pending'
    ) {
      return {
        approved_draft_id: draft.id,
        status: 'approved',
        outbox_queued: true,
      };
    }
    throw new ApproveError('server', 'Сервер вернул ответ неожиданного формата');
  }

  if (status === 409) {
    const approvedId =
      data !== null && typeof data.approved_draft_id === 'string' && data.approved_draft_id !== ''
        ? data.approved_draft_id
        : null;
    throw new ApproveError('conflict', 'Another draft is already approved for this review', approvedId);
  }

  if (status === 403) throw new ApproveError('forbidden', 'Недостаточно прав для публикации ответа');
  if (status === 400 || status === 422) {
    throw new ApproveError('validation', 'Текст ответа не прошёл проверку');
  }
  throw new ApproveError('server', `Ошибка сервера (${status})`);
}
