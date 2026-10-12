import assert from 'node:assert/strict';
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';

import { createApiClient, QuotaExceededApiError, ApiError } from './client.ts';
import { parseQuotaExceeded, quotaStore } from './quota.ts';
import { TokenStore } from './token.ts';

function respond(status: number, data: unknown, headers: Record<string, string> = {}): AxiosAdapter {
  return (config: InternalAxiosRequestConfig) => {
    const response = { data, status, statusText: '', headers, config, request: {} };
    if (status >= 200 && status < 300) return Promise.resolve(response);
    return Promise.reject(new AxiosError('fail', 'ERR_BAD_REQUEST', config, {}, response as never));
  };
}
const mk = (adapter: AxiosAdapter, onUnauthorized?: () => void) =>
  createApiClient({ baseURL: 'http://api.test', tokens: new TokenStore(null), adapter, onUnauthorized });

let n = 0;
async function t(name: string, fn: () => Promise<void> | void) {
  quotaStore.dismiss();
  await fn();
  n += 1;
  console.log('ok', name);
}

await t('check_quota format → store + typed error', async () => {
  const seen: unknown[] = [];
  const unsub = quotaStore.subscribe(() => seen.push(quotaStore.getSnapshot()));
  const body = { detail: { code: 'quota_exceeded', message: 'Лимит', requests_used: 1000, max_requests: 1000 } };
  const api = mk(respond(402, body, { 'x-correlation-id': 'cid-1' }));
  await assert.rejects(api.get('/x'), (e: unknown) => {
    assert.ok(e instanceof QuotaExceededApiError);
    assert.equal(e.info.maxRequests, 1000);
    assert.equal(e.correlationId, 'cid-1');
    return true;
  });
  assert.deepEqual(quotaStore.getSnapshot(), {
    code: 'quota_exceeded', message: 'Лимит', requestsUsed: 1000, maxRequests: 1000, resetDate: undefined, correlationId: 'cid-1',
  });
  assert.equal(seen.length, 1);
  unsub();
});

await t('QuotaService format', async () => {
  const api = mk(respond(402, { detail: { error: 'quota_exceeded', used: 5, limit: 5, reset_date: '2026-11-01', message: 'm' } }));
  await assert.rejects(api.get('/x'));
  const s = quotaStore.getSnapshot()!;
  assert.deepEqual([s.requestsUsed, s.maxRequests, s.resetDate], [5, 5, '2026-11-01']);
});

await t('subscription_inactive code passes through', async () => {
  await assert.rejects(mk(respond(402, { detail: { code: 'subscription_inactive', message: 'off' } })).get('/x'));
  assert.equal(quotaStore.getSnapshot()?.code, 'subscription_inactive');
});

await t('unrecognised bodies still open the dialog with defaults', async () => {
  for (const body of ['Payment Required', '', null, { detail: 42 }, { detail: 'text' }]) {
    quotaStore.dismiss();
    await assert.rejects(mk(respond(402, body)).get('/x'));
    assert.ok(quotaStore.getSnapshot()?.message.length);
  }
});

await t('burst of 402 keeps the first, notifies once', async () => {
  let notified = 0;
  quotaStore.subscribe(() => (notified += 1));
  const api = mk(respond(402, { detail: { code: 'quota_exceeded', message: 'first' } }));
  await Promise.allSettled([api.get('/a'), api.get('/b'), api.get('/c')]);
  assert.equal(notified, 1);
});

await t('skipQuotaDialog suppresses modal but still rejects typed', async () => {
  await assert.rejects(mk(respond(402, { detail: 'x' })).get('/x', { skipQuotaDialog: true }), QuotaExceededApiError);
  assert.equal(quotaStore.getSnapshot(), null);
});

await t('non-402 errors do not open the dialog; 401 clears token', async () => {
  let unauthorized = 0;
  await assert.rejects(mk(respond(500, { detail: 'boom' })).get('/x'), (e: unknown) => e instanceof ApiError && !(e instanceof QuotaExceededApiError));
  await assert.rejects(mk(respond(401, {}), () => (unauthorized += 1)).get('/x'));
  assert.equal(quotaStore.getSnapshot(), null);
  assert.equal(unauthorized, 1);
});

await t('success passes through', async () => {
  const r = await mk(respond(200, { ok: true })).get('/x');
  assert.deepEqual(r.data, { ok: true });
});

await t('dismiss then new 402 reopens', async () => {
  const api = mk(respond(402, { detail: { code: 'quota_exceeded', message: 'm' } }));
  await assert.rejects(api.get('/x'));
  quotaStore.dismiss();
  assert.equal(quotaStore.getSnapshot(), null);
  await assert.rejects(api.get('/x'));
  assert.notEqual(quotaStore.getSnapshot(), null);
});

assert.equal(parseQuotaExceeded(undefined).code, 'quota_exceeded');
console.log(`${n} passed`);
