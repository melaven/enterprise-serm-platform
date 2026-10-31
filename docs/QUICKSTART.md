# Tenable SERM Quick Start

## Requirements

- Docker Engine with Docker Compose v2
- Git

## Run the application

1. Copy `.env.example` to `.env`.
2. Set unique PostgreSQL, tenant-role, and Redis passwords. Set your Supabase
   URL and JWT secret, and URL-encode special characters in database passwords.
3. Validate configuration and start the services:

```shell
docker compose --env-file .env.example config
docker compose up --build
```

Compose starts PostgreSQL and Redis, applies migrations, then starts the API
and ARQ worker. The API is available at `http://127.0.0.1:8000`; shut down
with `docker compose down`.

For details, see the [local development guide](LOCAL_DEVELOPMENT.md), the
[Docker deployment guide](DOCKER_DEPLOYMENT.md), and the
[CI/CD guide](CI_CD_GUIDE.md).

- **Docker NOT used** - local development only
- **Disk space** - minimal (no .vhdx files)
- **Virtual environment** - created in `.venv/`
- **Environment files** - configure `.env` and `frontend/.env`

## 🐛 Troubleshooting

1. **Python not found:** Install Python 3.10+ from python.org
2. **Node.js not found:** Install Node.js 18+ from nodejs.org
3. **Import errors:** Activate virtual environment first
4. **Port 8000/3000 in use:** Change port in start script or kill process
5. **Database errors:** Check DATABASE_URL in `.env`
6. **Frontend can't reach backend:** Check VITE_API_BASE_URL in `frontend/.env`

## 📞 Support

See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for detailed troubleshooting.

---

**Version:** 1.1
**Last Updated:** 2026-10-14
