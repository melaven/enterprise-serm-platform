# Tenable SERM - Quick Start (Local Development)

## 🚀 One-Click Start (Recommended)

### Windows
```powershell
# 1. Setup environment (first time only)
.\setup_env.ps1
.\install_frontend.bat

# 2. Configure .env
copy .env.local.example .env
copy frontend\.env.example frontend\.env
# Edit .env with your settings (JWT_SECRET_KEY, OPENAI_API_KEY)

# 3. Start everything (backend + frontend)
.\start_all.bat
```

### Linux/Mac
```bash
# 1. Setup environment (first time only)
chmod +x setup_env.sh install_frontend.sh start_all.sh stop_all.sh
./setup_env.sh
./install_frontend.sh

# 2. Configure .env
cp .env.local.example .env
cp frontend/.env.example frontend/.env
# Edit .env with your settings

# 3. Start everything (backend + frontend)
./start_all.sh
```

## 📝 Individual Commands

| Command | Windows | Linux/Mac | Description |
|---------|---------|-----------|-------------|
| Setup Env | `.\setup_env.ps1` | `./setup_env.sh` | Install Python dependencies |
| Install Frontend | `.\install_frontend.bat` | `./install_frontend.sh` | Install npm dependencies |
| Start All | `.\start_all.bat` | `./start_all.sh` | Start backend + frontend |
| Stop All | `.\stop_all.bat` | `./stop_all.sh` | Stop all services |
| Start Backend | `.\start_backend.bat` | `./start_backend.sh` | Start FastAPI only |
| Run Tests | `.\run_tests.bat` | `./run_tests.sh` | Run pytest with coverage |
| Run Linting | `.\run_lint.bat` | `./run_lint.sh` | Check code quality |
| Format Code | `.\format_code.bat` | `ruff format app/ tests/` | Format with Ruff |

## 🔧 Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- Git
- Code Editor (VS Code recommended)

## 📚 Documentation

- **Local Development Guide:** [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md)
- **Docker Deployment:** [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md)
- **CI/CD Pipeline:** [CI_CD_GUIDE.md](CI_CD_GUIDE.md)
- **High-Performance Architecture:** [HIGH_PERFORMANCE_ARCHITECTURE.md](HIGH_PERFORMANCE_ARCHITECTURE.md)

## 🎯 Quick Tips

### Database
- **Easiest:** SQLite (no setup required)
- **Recommended:** PostgreSQL (install locally or use Docker for DB only)

### Redis
- **Skip for local dev:** Set `REDIS_URL=dummy://skip` in `.env`
- **Use locally:** Install Memurai (Windows) or Redis (Linux/Mac)

### API Endpoints
- **Backend:** http://127.0.0.1:8000
- **Frontend:** http://localhost:3000
- **API Docs:** http://127.0.0.1:8000/docs
- **Health Check:** http://127.0.0.1:8000/health

## ⚠️ Important Notes

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
