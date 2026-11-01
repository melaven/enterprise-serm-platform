import { ApiError } from '@/api/client';
import { apiClient } from '@/api/services';
import {
  ApproveError,
  approveEndpoint,
  interpretApproveResponse,
  type ApproveRequest,
  type ApproveResult,
} from './approveDraftLogic.ts';

/**
 * Реальный апрув черновика. Используйте как `onApprove` для AntiCrisisRadar.
 *
 * validateStatus позволяет разобрать контрактные 4xx-ответы, включая 409.
 * 401 по-прежнему идёт через interceptor (сброс токена + редирект на логин).
 */
export async function approveDraft(request: ApproveRequest, signal?: AbortSignal): Promise<ApproveResult> {
  try {
    const response = await apiClient.post<unknown>(
      approveEndpoint(request.reviewId, request.draftId),
      { edited_text: request.content },
      {
        validateStatus: (status: number) => status < 500 && status !== 401,
        ...(signal ? { signal } : {}),
      },
    );
    return interpretApproveResponse(response.status, response.data);
  } catch (error: unknown) {
    if (error instanceof ApproveError) throw error;
    if (error instanceof ApiError) {
      throw new ApproveError(error.status === 0 ? 'network' : 'server', error.message);
    }
    throw new ApproveError('network', 'Нет соединения с сервером');
  }
}
