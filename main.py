from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Импортируем наш боевой роутер отзывов
from app.app.routers.reviews import router as reviews_router

app = FastAPI(
    title="Tenable SI Core",
    description="Autonomous SI SERM & Reputation Engine (Tenable)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Разрешаем CORS (чтобы запросы от n8n, сторонних скриптов или фронтенда не блокировались)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутер обработки отзывов
app.include_router(reviews_router)

@app.get("/health", tags=["System"])
async def health_check():
    """Эндпоинт для проверки жизнеспособности сервера"""
    return {"status": "healthy", "service": "Tenable SI Engine"}
