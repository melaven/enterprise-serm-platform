import { describe, expect, it } from 'vitest';

import {
  ApproveError,
  approveEndpoint,
  canPublishCritical,
  interpretApproveResponse,
} from './approveDraftLogic.ts';

function catchApproveError(status: number, body: unknown): ApproveError {
  try {
    interpretApproveResponse(status, body);
  } catch (error) {
    if (error instanceof ApproveError) return error;
    throw error;
  }
  throw new Error('ожидалась ошибка');
}

describe('approve draft response', () => {
  it('maps the backend response, including an idempotent approval', () => {
    const body = {
      draft: { id: 'd1', is_approved: true },
      idempotent: true,
      publication_status: 'outbox_pending',
    };
    expect(interpretApproveResponse(200, body)).toEqual({
      approved_draft_id: 'd1',
      status: 'approved',
      outbox_queued: true,
    });
  });

  it('treats a malformed success response as a server error', () => {
    expect(catchApproveError(200, { status: 'approved' }).kind).toBe('server');
    expect(catchApproveError(200, null).kind).toBe('server');
    expect(catchApproveError(200, {
      draft: { id: '', is_approved: true },
      idempotent: false,
      publication_status: 'outbox_pending',
    }).kind).toBe('server');
  });

  it('reports a conflict even when the backend does not identify the approved draft', () => {
    const error = catchApproveError(409, { detail: 'Another response draft was approved' });
    expect(error.kind).toBe('conflict');
    expect(error.approvedDraftId).toBeNull();
  });

  it('maps forbidden, validation, and server errors', () => {
    expect(catchApproveError(403, {}).kind).toBe('forbidden');
    expect(catchApproveError(422, {}).kind).toBe('validation');
    expect(catchApproveError(500, undefined).kind).toBe('server');
    expect(catchApproveError(404, undefined).kind).toBe('server');
  });

  it('allows only owners and admins to publish critical responses', () => {
    expect(canPublishCritical('owner')).toBe(true);
    expect(canPublishCritical('admin')).toBe(true);
    expect(canPublishCritical('member')).toBe(false);
  });

  it('escapes identifiers in the endpoint', () => {
    expect(approveEndpoint('r/1', 'd 2')).toBe('/v1/reviews/r%2F1/drafts/d%202/approve');
  });
});
