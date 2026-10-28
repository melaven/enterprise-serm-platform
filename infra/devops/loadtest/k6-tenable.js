// k6 run -e BASE_URL=https://staging.example.com -e PROFILE=smoke loadtest/k6-tenable.js
// TOKENS_JSON='["<jwt tenant A>","<jwt tenant B>",...]'  (токены разных компаний; у каждого свой company_id в claims)
//
// Что доказываем (честно про архитектуру: Advisory Locks в коде нет; гарантии такие):
//   G1. Дедуп постановки: одинаковый (company, platform, url) -> детерминированный job_id -> ровно один 202, остальные 409.
//   G2. Квота не превышается при гонке: резерв атомарный (consume_quota в воркере). В teardown сверяем used <= limit.
//   G3. Пул соединений (pool_size + max_overflow=0): при 1000 VU нет каскада 5xx и зависаний, p95 в рамках,
//       перегрузка деградирует в 429/503 с быстрым ответом, а не в таймауты.
//   G4. Изоляция: токен tenant A никогда не видит данные tenant B (company_id в ответах == свой).
import http from 'k6/http';
import { check, sleep, fail } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import exec from 'k6/execution';

const BASE = __ENV.BASE_URL || fail('BASE_URL required');
const PROFILE = __ENV.PROFILE || 'smoke';
const PLATFORM = __ENV.PLATFORM || 'google';
// Шаблон URL, чей хост проходит host_allowed(platform). {n} подставляется.
const URL_TEMPLATE = __ENV.URL_TEMPLATE || 'https://www.google.com/maps/place/loadtest-{n}';
const JOBS_PATH = __ENV.JOBS_PATH || '/api/v1/parser/jobs';
const REVIEWS_PATH = __ENV.REVIEWS_PATH || '/api/v1/reviews';
const SUMMARY_PATH = __ENV.SUMMARY_PATH || '/api/v1/reviews/summary';
const RUN_ID = __ENV.RUN_ID || `${Date.now()}`;   // свежие URL на каждый прогон (иначе job_id уже занят)

const tokens = new SharedArray('tokens', () => {
  const t = JSON.parse(__ENV.TOKENS_JSON || '[]');
  if (!t.length) throw new Error('TOKENS_JSON: нужен массив JWT');
  return t;
});

const full = PROFILE === 'full';
const PEAK = full ? 1000 : 50;

export const options = {
  scenarios: {
    // G3 + G4: чтение, до 1000 одновременных пользователей
    browse: {
      executor: 'ramping-vus',
      exec: 'browse',
      startVUs: 0,
      stages: [
        { duration: full ? '2m' : '20s', target: PEAK / 2 },
        { duration: full ? '5m' : '40s', target: PEAK },
        { duration: full ? '1m' : '10s', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
    // G1: все VU бьют один и тот же URL одного tenant'а одновременно
    dup_burst: {
      executor: 'per-vu-iterations',
      exec: 'dupBurst',
      vus: full ? 200 : 20,
      iterations: 1,
      startTime: full ? '2m' : '15s',   // во время плато
      maxDuration: '1m',
    },
    // G2: гонка за квоту одного tenant'а: много РАЗНЫХ url параллельно
    quota_race: {
      executor: 'constant-arrival-rate',
      exec: 'quotaRace',
      rate: full ? 100 : 10,
      timeUnit: '1s',
      duration: full ? '1m' : '10s',
      preAllocatedVUs: full ? 150 : 20,
      maxVUs: full ? 300 : 40,
      startTime: full ? '3m' : '20s',
    },
  },
  thresholds: {
    // нет 5xx вообще: пул/блокировки не должны превращаться в 500/502/504
    status_5xx: ['rate<0.001'],
    // 402/409/429 — штатные ответы, не ошибки
    http_req_failed: ['rate<0.01'],
    'http_req_duration{scenario:browse}': ['p(95)<1000', 'p(99)<2500'],
    // G1: за весь прогон принято не более одной постановки на дублирующий URL
    dup_accepted: ['count<=1'],
    tenant_leaks: ['count==0'],
    checks: ['rate>0.99'],
  },
  summaryTrendStats: ['avg', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

// штатные статусы не считаются ошибкой http_req_failed
http.setResponseCallback(http.expectedStatuses(200, 202, 402, 409, 429));

const status5xx = new Rate('status_5xx');
const dupAccepted = new Counter('dup_accepted');
const dupConflict = new Counter('dup_conflict');
const quotaAccepted = new Counter('quota_accepted');
const quotaRejected = new Counter('quota_rejected_402');
const tenantLeaks = new Counter('tenant_leaks');
const shed = new Counter('load_shed_429_503');
const reviewsLatency = new Trend('reviews_latency', true);

const tokenFor = (i) => tokens[i % tokens.length];
const headers = (t) => ({ headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json', 'X-Correlation-ID': `k6-${RUN_ID}-${exec.vu.idInTest}-${exec.scenario.iterationInTest}` } });
const jwtCompany = (t) => {
  try {
    const p = t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(encoding.b64decode(p, 'rawstd', 's')).company_id;
  } catch (_) { return null; }
};
import encoding from 'k6/encoding';

function track(res) {
  status5xx.add(res.status >= 500);
  if (res.status === 429 || res.status === 503) shed.add(1);
}

export function browse() {
  const t = tokenFor(exec.vu.idInTest);
  const res = http.get(`${BASE}${REVIEWS_PATH}?limit=20&offset=${Math.floor(Math.random() * 5) * 20}`, { ...headers(t), tags: { name: 'GET reviews' } });
  track(res);
  reviewsLatency.add(res.timings.duration);
  check(res, { 'reviews 200|429': (r) => r.status === 200 || r.status === 429 });
  if (res.status === 200) {
    const own = jwtCompany(t);
    let body = [];
    try { const j = res.json(); body = Array.isArray(j) ? j : (j.data && (j.data.items || j.data)) || []; } catch (_) {}
    if (own && Array.isArray(body) && body.some((r) => r.company_id && r.company_id !== own)) tenantLeaks.add(1);
  }
  sleep(0.5 + Math.random());
}

export function dupBurst() {
  const t = tokenFor(0);   // один tenant, один URL
  const url = URL_TEMPLATE.replace('{n}', `dup-${RUN_ID}`);
  const res = http.post(`${BASE}${JOBS_PATH}`, JSON.stringify({ platform: PLATFORM, url }), { ...headers(t), tags: { name: 'POST jobs (dup)' } });
  track(res);
  if (res.status === 202) dupAccepted.add(1);
  if (res.status === 409) dupConflict.add(1);
  check(res, { 'dup: 202|409|402|429': (r) => [202, 409, 402, 429].includes(r.status) });
}

export function quotaRace() {
  const t = tokenFor(Number(__ENV.QUOTA_TENANT_INDEX || 1));   // tenant с малой квотой (например, лимит 50)
  const n = `q-${RUN_ID}-${exec.scenario.iterationInTest}`;
  const res = http.post(`${BASE}${JOBS_PATH}`, JSON.stringify({ platform: PLATFORM, url: URL_TEMPLATE.replace('{n}', n) }), { ...headers(t), tags: { name: 'POST jobs (quota)' } });
  track(res);
  if (res.status === 202) quotaAccepted.add(1);
  if (res.status === 402) quotaRejected.add(1);
  check(res, { 'quota: 202|402|409|429': (r) => [202, 402, 409, 429].includes(r.status) });
}

// После прогона ждём, пока воркер разберёт очередь, и проверяем главный инвариант: used <= limit.
export function teardown() {
  const t = tokenFor(Number(__ENV.QUOTA_TENANT_INDEX || 1));
  const deadline = Date.now() + 120000;
  let last = null;
  while (Date.now() < deadline) {
    const r = http.get(`${BASE}${SUMMARY_PATH}`, headers(t));
    if (r.status === 200) {
      try {
        const d = r.json().data || r.json();
        const used = d.requests_used ?? d.reviews_used, limit = d.max_requests ?? d.reviews_limit;
        if (used !== undefined && limit !== undefined) {
          last = { used, limit };
          if (used > limit) fail(`QUOTA OVERRUN: used=${used} > limit=${limit}`);
        }
      } catch (_) {}
    }
    sleep(5);
  }
  console.log(`quota invariant: ${last ? `used=${last.used} limit=${last.limit} OK` : 'поля summary не найдены — проверь SUMMARY_PATH/названия полей'}`);
}
