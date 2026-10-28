# Нагрузочный тест (k6)
```bash
export TOKENS_JSON='["<jwt A>","<jwt B>", ...]'     # >= 20 токенов разных tenant'ов; токен [1] — tenant с малой квотой (50)
k6 run -e BASE_URL=https://staging.example.com -e PROFILE=smoke loadtest/k6-tenable.js   # сначала smoke (50 VU)
k6 run -e BASE_URL=https://staging.example.com -e PROFILE=full  loadtest/k6-tenable.js   # 1000 VU
```
Условия, без которых цифры бессмысленны:
- Только staging. Воркер на staging должен работать со стабом скрапера (иначе нагрузка уйдёт на реальные площадки).
- Генератор нагрузки — отдельная машина, её IP в allowlist `limit_req`, иначе nginx отдаст 429 и вы протестируете rate limit, а не пул.
- Пул: `pool_size=10, max_overflow=0` (API sessions) — при 1000 VU ожидаем очередь на пул; смотрите `reviews_latency` и `load_shed_429_503`.
- Пороги (`thresholds`) — стартовые гипотезы, подберите по результатам smoke.
