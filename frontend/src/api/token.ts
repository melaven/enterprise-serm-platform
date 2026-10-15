/**
 * Хранение и разбор JWT. Без зависимостей от DOM/axios: тестируется в Node.
 *
 * Порядок поиска токена:
 *   1. память (после set(): самый безопасный источник, недоступен чужим вкладкам);
 *   2. наш ключ `serm.access_token` в storage;
 *   3. сессия supabase-js (`sb-<project>-auth-token`), если фронт логинится через неё.
 *
 * Про безопасность: токен в localStorage читается любым XSS. Для продакшена
 * лучше держать access-токен только в памяти (set(token, { persist: false })) и
 * обновлять его через refresh-токен в httpOnly-cookie. Хранилище здесь абстрактно
 * ровно для того, чтобы это можно было сменить без правок клиента.
 */

export interface KeyValueStorage {
  readonly length: number;
  key(index: number): string | null;
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const OWN_TOKEN_KEY = 'serm.access_token';
const SUPABASE_KEY = /^sb-.+-auth-token$/;
const EXPIRY_SKEW_S = 10;

export type JwtClaims = Record<string, unknown>;

/** Разбор payload без проверки подписи: только для UX (срок, tenant). Доверяет токену сервер. */
export function decodeJwtClaims(token: string): JwtClaims | null {
  const parts = token.split('.');
  const payload = parts[1];
  if (parts.length !== 3 || payload === undefined) return null;
  try {
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const bytes = Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
    const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes));
    return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? (parsed as JwtClaims)
      : null;
  } catch {
    return null;
  }
}

/** true, если у токена есть exp и он уже прошёл (с запасом на расхождение часов). */
export function isExpired(token: string, nowMs: number): boolean {
  const exp = decodeJwtClaims(token)?.['exp'];
  return typeof exp === 'number' && exp - EXPIRY_SKEW_S <= nowMs / 1000;
}

export function tenantIdFromToken(token: string): string | null {
  const tenant = decodeJwtClaims(token)?.['tenant_id'];
  return typeof tenant === 'string' && tenant !== '' ? tenant : null;
}

function readSupabaseToken(storage: KeyValueStorage): string | null {
  for (let i = 0; i < storage.length; i += 1) {
    const key = storage.key(i);
    if (key === null || !SUPABASE_KEY.test(key)) continue;
    try {
      const session: unknown = JSON.parse(storage.getItem(key) ?? 'null');
      if (typeof session === 'object' && session !== null) {
        const access = (session as { access_token?: unknown }).access_token;
        if (typeof access === 'string' && access !== '') return access;
      }
    } catch {
      // битый JSON в чужом ключе: пропускаем
    }
  }
  return null;
}

export interface SetTokenOptions {
  /** true (по умолчанию): дополнительно сохранить в storage. */
  persist?: boolean;
}

export class TokenStore {
  private memory: string | null = null;
  private readonly storage: KeyValueStorage | null;
  private readonly now: () => number;

  constructor(storage: KeyValueStorage | null, now: () => number = Date.now) {
    this.storage = storage;
    this.now = now;
  }

  /** Актуальный (не просроченный) токен или null. */
  get(): string | null {
    const candidates = [
      this.memory,
      this.storage?.getItem(OWN_TOKEN_KEY) ?? null,
      this.storage ? readSupabaseToken(this.storage) : null,
    ];
    for (const token of candidates) {
      if (token !== null && token !== '' && !isExpired(token, this.now())) return token;
    }
    return null;
  }

  set(token: string, options: SetTokenOptions = {}): void {
    this.memory = token;
    if (options.persist !== false) this.storage?.setItem(OWN_TOKEN_KEY, token);
  }

  /** Выход / 401: чистим память и наш ключ (сессию supabase-js не трогаем: её ведёт SDK). */
  clear(): void {
    this.memory = null;
    this.storage?.removeItem(OWN_TOKEN_KEY);
  }
}

/**
 * Токен уходит только на наш API: относительные URL или тот же origin, что у baseURL.
 * Иначе, например, `api.get('https://evil.example/x')` отправил бы JWT на чужой хост.
 */
export function shouldAttachToken(
  requestUrl: string | undefined,
  baseUrl: string | undefined,
  pageOrigin: string,
): boolean {
  try {
    const apiOrigin = new URL(baseUrl ?? '', pageOrigin).origin;
    return new URL(requestUrl ?? '', new URL(baseUrl ?? '', pageOrigin)).origin === apiOrigin;
  } catch {
    return false;
  }
}
