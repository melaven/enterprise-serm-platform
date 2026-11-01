import type { UserRole } from './approveDraftLogic';

const USER_ROLES = ['owner', 'admin', 'member'] as const satisfies readonly UserRole[];

function isUserRole(role: unknown): role is UserRole {
  return USER_ROLES.some((candidate) => candidate === role);
}

export function getCompanyRoleFromToken(token: string | null): UserRole | null {
  if (token === null) return null;

  const encodedPayload = token.split('.')[1];
  if (encodedPayload === undefined) return null;

  try {
    const base64 = encodedPayload.replace(/-/g, '+').replace(/_/g, '/');
    const paddedBase64 = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const payload: unknown = JSON.parse(atob(paddedBase64));
    if (typeof payload !== 'object' || payload === null || !('company_role' in payload)) return null;

    return isUserRole(payload.company_role) ? payload.company_role : null;
  } catch {
    return null;
  }
}
