# Docker Deployment

## Local development

Requirements: Docker Engine and Docker Compose v2.

1. Copy `.env.example` to `.env`.
2. Set unique PostgreSQL, tenant-role, and Redis passwords. Set `SUPABASE_URL`
   and `SUPABASE_JWT_SECRET`; URL-encode special characters in database URLs.
3. Validate the example configuration and start the stack:

```shell
docker compose --env-file .env.example config
docker compose up --build
```

Compose starts PostgreSQL and Redis on an internal network, runs database
migrations with the admin connection, then starts the API and separate bulk and
critical ARQ workers with the restricted tenant role. Only the API is published, bound to
`127.0.0.1:8000` by default. Set `API_PORT` in `.env` to change the host port.

```shell
docker compose ps
docker compose logs -f api worker worker-critical
docker compose down
```

For a rolling migration from the old default ARQ queue, start its compatibility
worker until the queue is empty, then stop it:

```shell
docker compose --profile queue-migration up -d worker-legacy
docker compose exec redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli ZCARD arq:queue'
docker compose --profile queue-migration stop worker-legacy
```

Named volumes preserve PostgreSQL and Redis data. `docker compose down -v`
deletes that data.

## Production

`docker-compose.prod.yml` runs the API, bulk and critical workers, PostgreSQL, Redis, and Nginx
reverse proxy. Configure `.env` using `.env.example`, including `SERVER_NAME`,
`TLS_CERT_DIR`, and production credentials, then run:

```shell
docker compose -f docker-compose.prod.yml --env-file .env config
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

Nginx publishes ports 80 and 443; API, PostgreSQL, and Redis are not published
to the host. The Compose migration service runs before the API and workers.
For automated deployment and certificate setup, see
[`PRODUCTION_SETUP.md`](PRODUCTION_SETUP.md) and [`../scripts/deploy.sh`](../scripts/deploy.sh).

## Images and CI

The root `Dockerfile` builds one Python image used by migrations, the API, and
the ARQ worker; Compose selects each role's command. `frontend/Dockerfile`
builds the standalone frontend image. The GitHub Actions workflow at
`.github/workflows/main.yml` validates Compose configuration and builds the
images.

## Troubleshooting

```shell
docker compose ps
docker compose logs --tail=100 api worker migrate
docker compose exec redis redis-cli -a "$REDIS_PASSWORD" ping
```

If a service fails to start, check `.env` and the health status of its
dependencies. Database migrations must complete successfully before the API
or worker can start.
