import assert from 'node:assert/strict';
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';

import { ApiError, createApiClient, QuotaExceededApiError } from './client.ts';
import { createParserApi, isAbortError, waitForJob, type ParseJobStatus } from './parser.ts';
import { quotaStore } from './quota.ts';
import { TokenStore } from './token.ts';

type Handler = (config: InternalAxiosRequestConfig) => { status: number; data: unknown };

function setup(handler: Handler) {
  const calls: InternalAxiosRequestConfig[] = [];
  const adapter: AxiosAdapter = (config) => {
    calls.push(config);
    const { status, data } = handler(config);
    const response = { data, status, statusText: '', headers: {}, config, request: {} };
    return status < 300
      ? Promise.resolve(response)
      : Promise.reject(new AxiosError('fail', 'ERR_BAD_REQUEST', config, {}, response as never));
  };
  const client = createApiClient({ baseURL: 'http://api.test', tokens: new TokenStore(null), adapter });
  return { parser: createParserApi(client), calls };
}

const job = (state: ParseJobStatus['state']): ParseJobStatus => ({ job_id: 'j', state, result: null, error: null });
const noSleep = () => Promise.resolve();
let n = 0;
async function t(name: string, fn: () => Promise<void>) {
  quotaStore.dismiss();
  await fn();
  n += 1;
  console.log('ok', name);
}

await t('start posts to /api/v1/parser/start through the interceptor client', async () => {
  const { parser, calls } = setup(() => ({ status: 202, data: { job_id: 'parse:t:trustpilot:abc', status: 'queued' } }));
  assert.equal(await parser.start('trustpilot', 'https://www.trustpilot.com/review/x.com'), 'parse:t:trustpilot:abc');
  assert.equal(calls[0]?.url, '/api/v1/parser/start');
  assert.deepEqual(JSON.parse(String(calls[0]?.data)), { platform: 'trustpilot', url: 'https://www.trustpilot.com/review/x.com' });
});

await t('402 on start opens the global modal and rejects typed', async () => {
  const { parser } = setup(() => ({
    status: 402,
    data: { detail: { code: 'quota_exceeded', message: 'Лимит', requests_used: 1000, max_requests: 1000 } },
  }));
  await assert.rejects(parser.start('yandex', 'https://yandex.ru/maps/org/1'), QuotaExceededApiError);
  assert.equal(quotaStore.getSnapshot()?.maxRequests, 1000);
});

await t('409 is a plain ApiError and does not open the modal', async () => {
  const { parser } = setup(() => ({ status: 409, data: { detail: 'already queued' } }));
  await assert.rejects(parser.start('2gis', 'https://2gis.ru/x'), (e: unknown) => e instanceof ApiError && !(e instanceof QuotaExceededApiError) && e.status === 409);
  assert.equal(quotaStore.getSnapshot(), null);
});

await t('status request encodes job id and never opens the modal', async () => {
  const { parser, calls } = setup(() => ({ status: 402, data: { detail: 'x' } }));
  await assert.rejects(parser.status('parse:t:g:1'));
  assert.equal(calls[0]?.url, '/api/v1/parser/jobs/parse%3At%3Ag%3A1');
  assert.equal(quotaStore.getSnapshot(), null);
});

await t('waitForJob polls until succeeded', async () => {
  const seq: ParseJobStatus['state'][] = ['queued', 'in_progress', 'succeeded'];
  let i = 0;
  const { parser } = setup(() => ({ status: 200, data: job(seq[i++] ?? 'succeeded') }));
  const ticks: string[] = [];
  const final = await waitForJob(parser, 'j', { sleep: noSleep, onTick: (s) => ticks.push(s.state) });
  assert.equal(final.state, 'succeeded');
  assert.deepEqual(ticks, seq);
});

await t('failed is returned, not thrown', async () => {
  const { parser } = setup(() => ({ status: 200, data: job('failed') }));
  assert.equal((await waitForJob(parser, 'j', { sleep: noSleep })).state, 'failed');
});

await t('404 throws immediately', async () => {
  const { parser, calls } = setup(() => ({ status: 404, data: { detail: 'nf' } }));
  await assert.rejects(waitForJob(parser, 'j', { sleep: noSleep }), (e: unknown) => e instanceof ApiError && e.status === 404);
  assert.equal(calls.length, 1);
});

await t('transient 5xx tolerated, then success; persistent one throws', async () => {
  let i = 0;
  const flaky = setup(() => (i++ < 2 ? { status: 503, data: {} } : { status: 200, data: job('succeeded') }));
  assert.equal((await waitForJob(flaky.parser, 'j', { sleep: noSleep })).state, 'succeeded');
  const dead = setup(() => ({ status: 503, data: {} }));
  await assert.rejects(waitForJob(dead.parser, 'j', { sleep: noSleep, maxTransientErrors: 2 }), ApiError);
  assert.equal(dead.calls.length, 3);
});

await t('timeout and abort', async () => {
  const { parser } = setup(() => ({ status: 200, data: job('in_progress') }));
  await assert.rejects(waitForJob(parser, 'j', { sleep: noSleep, intervalMs: 10, timeoutMs: 5 }), /время ожидания/);
  const ac = new AbortController();
  ac.abort();
  const aborted = setup(() => ({ status: 200, data: job('queued') }));
  await assert.rejects(waitForJob(aborted.parser, 'j', { signal: ac.signal, intervalMs: 5 }), (e: unknown) => isAbortError(e));
});

console.log(`${n} passed`);
