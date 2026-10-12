import assert from 'node:assert/strict';
import { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios';

import { createApiClient } from './client.ts';
import { quotaStore } from './quota.ts';
import { createReviewsApi, mapReview, mapSummary } from './reviews.ts';
import { TokenStore } from './token.ts';

function setup(status: number, data: unknown) {
  const calls: InternalAxiosRequestConfig[] = [];
  const adapter: AxiosAdapter = (config) => {
    calls.push(config);
    const response = { data, status, statusText: '', headers: {}, config, request: {} };
    return status < 300
      ? Promise.resolve(response)
      : Promise.reject(new AxiosError('fail', 'ERR_BAD_REQUEST', config, {}, response as never));
  };
  const client = createApiClient({ baseURL: 'http://api.test', tokens: new TokenStore(null), adapter });
  return { api: createReviewsApi(client), calls };
}
let n = 0;
async function t(name: string, fn: () => Promise<void>) {
  quotaStore.dismiss();
  await fn();
  n++;
  console.log(`ok ${n} ${name}`);
}

await t('mapReview: body → text, rating 0 → null, defaults', async () => {
  const r = mapReview({ id: '1', platform: 'yandex', body: 'hi', rating: 0 });
  assert.equal(r.text, 'hi');
  assert.equal(r.rating, null);
  assert.deepEqual(r.ai_tags, []);
  assert.equal(r.is_critical, false);
  assert.equal(r.ai_pending, false);
});

await t('mapSummary: reviews|count → count, missing counters → null', async () => {
  const s = mapSummary({
    total_reviews: 3,
    average_rating: 4,
    sentiment: { positive: 1, neutral: 1, negative: 1, unclassified: 0 },
    timeline: [{ date: '2026-10-01', reviews: 2 }, { date: '2026-10-02', count: 1 }],
    period: { date_from: '2026-10-01', date_to: '2026-10-02' },
  });
  assert.deepEqual(s.timeline.map((p) => p.count), [2, 1]);
  assert.equal(s.critical_reviews, null);
  assert.equal(s.ai_pending, null);
  assert.match(s.period ?? '', /01\.10.*02\.10/);
});

await t('list: limit/offset params, items mapped', async () => {
  const { api, calls } = setup(200, { items: [{ id: 'a', platform: 'google', body: 'x' }], total: 41 });
  const page = await api.list({ limit: 20, offset: 20 });
  assert.equal(calls[0]?.url, '/api/v1/reviews');
  assert.deepEqual(calls[0]?.params, { limit: 20, offset: 20 });
  assert.equal(page.total, 41);
  assert.equal(page.items[0]?.text, 'x');
});

await t('summary: GET /api/v1/reviews/summary', async () => {
  const { api, calls } = setup(200, {
    total_reviews: 0, average_rating: null,
    sentiment: { positive: 0, neutral: 0, negative: 0, unclassified: 0 }, timeline: [],
  });
  const s = await api.summary();
  assert.equal(calls[0]?.url, '/api/v1/reviews/summary');
  assert.equal(s.total_reviews, 0);
});

await t('402 on list opens quota dialog and rejects', async () => {
  const { api } = setup(402, { detail: { message: 'limit' } });
  await assert.rejects(api.list({ limit: 20, offset: 0 }));
  assert.equal(quotaStore.getSnapshot() !== null, true);
});
