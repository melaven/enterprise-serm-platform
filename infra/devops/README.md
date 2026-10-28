# Tenable — Infra & CI/CD

```
infra/terraform/   Hetzner: сервер + firewall + volume + cloud-init (docker, ssh-hardening, fail2ban, ufw)
deploy/            docker-compose.prod.yml (api, worker, redis, [postgres], caddy-TLS), deploy.sh (авто-rollback)
.github/workflows/ production.yml (ruff -> pytest -> terraform validate/Trivy config -> build -> Trivy image gate -> cosign -> deploy)
                   loadtest.yml  (ручной k6 против staging)
loadtest/          k6-tenable.js
```

## Запуск «одной командой»
```bash
export TF_VAR_hcloud_token=...                 # Hetzner Cloud API
cd infra/devops/infra/terraform && cp terraform.tfvars.example terraform.tfvars   # заполнить
terraform init && terraform apply              # создаёт сервер; затем A-запись DOMAIN -> output server_ipv4
ssh-keyscan -t ed25519 <ip>                    # -> GitHub Secret DEPLOY_KNOWN_HOSTS
git push origin main                           # CI: тесты -> образ -> Trivy -> апрув -> деплой
```
GitHub Secrets: `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`, `DEPLOY_HOST`, `PROD_ENV_FILE` (весь .env: DATABASE_URL, SUPABASE_URL, GEMINI_API_KEY, REDIS_PASSWORD…), `GHCR_TOKEN` (read:packages), `LOADTEST_TOKENS_JSON`. Variables: `DOMAIN`, `STAGING_URL`. Environment `production` -> Required reviewers.

## Что нужно в репозитории, чтобы пайплайн прошёл (в загруженном дереве этого НЕТ)
1. `requirements.txt` (Dockerfile и CI его используют) — в дереве только `requirements-dev.txt`/`-bot.txt`.
2. `app/main.py` (`app.main:app`) и эндпоинт `GET /health` (healthcheck compose, Caddy, smoke).
3. `ruff format --check` упадёт на неотформатированном коде: один раз прогнать `ruff format .`.
4. Postgres: прод — Supabase (migrations/001,002 зависят от схемы `auth`). Профиль `selfhosted-db` — только для стендов и требует shim схемы `auth`.
