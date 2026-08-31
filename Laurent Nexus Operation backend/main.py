import os

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Импортируем наш боевой роутер отзывов
from app.app.routers.reviews import router as reviews_router


class LeadSchema(BaseModel):
    email: str


app = FastAPI(
    title="Laurent Nexus Operation Backend",
    description="Autonomous AI SERM & Lead Engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Разрешаем CORS для локального фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутер обработки отзывов
app.include_router(reviews_router)


@app.post("/api/lead")
async def create_lead(lead: LeadSchema):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        return {"status": "success"}

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"🚨 Новая заявка!\nEmail: {lead.email}",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(telegram_url, json=payload)

    return {"status": "success"}


@app.get("/health", tags=["System"])
async def health_check():
    """Эндпоинт для проверки жизнеспособности сервера"""
    return {"status": "healthy", "service": "Laurent Nexus Engine"}
