"""BFF-слой авторизации: JWT живёт ТОЛЬКО в HttpOnly-cookie, JS его не видит.

Схема
  access  : cookie `__Host-tn_at`  HttpOnly; Secure; SameSite=Lax; Path=/            (TTL = exp токена)
  refresh : cookie `__Host-tn_rt`  HttpOnly; Secure; SameSite=Strict; Path=/ (см. REFRESH_PATH ниже)
  csrf    : cookie `tn_csrf`       НЕ HttpOnly (читает JS) + заголовок X-CSRF-Token (double-submit, HMAC-подписан)

`__Host-` префикс: браузер примет cookie только с Secure, Path=/ и БЕЗ Domain -> нельзя подсадить с поддомена.
Refresh-cookie с Path=/ (требование __Host-); защиту даёт SameSite=Strict + CSRF-проверка на POST /auth/refresh.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, SecretStr

from app.core.config import Settings, get_settings

AT, RT, CSRF = "__Host-tn_at", "__Host-tn_rt", "tn_csrf"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


# ---------- CSRF (double-submit, подписанный) ----------
def _sign(secret: str, nonce: str) -> str:
    return hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def new_csrf_token(secret: str) -> str:
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}.{_sign(secret, nonce)}"


def csrf_valid(secret: str, cookie: str | None, header: str | None) -> bool:
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        return False
    nonce, _, sig = cookie.partition(".")
    return bool(nonce) and hmac.compare_digest(sig, _sign(secret, nonce))


async def require_csrf(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Dependency для всех мутирующих роутов (или глобально: FastAPI(dependencies=[Depends(require_csrf)]))."""
    if request.method in SAFE_METHODS:
        return
    # Bearer-запросы (серверные интеграции) CSRF не подвержены: браузер не добавляет их сам.
    if request.headers.get("authorization", "").lower().startswith("bearer "):
        return
    if not csrf_valid(settings.csrf_secret, request.cookies.get(CSRF), request.headers.get("x-csrf-token")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF check failed")
    origin = request.headers.get("origin")  # второй рубеж: Origin обязан быть нашим
    if origin is not None and origin not in settings.cors_origins_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bad origin")


# ---------- cookies ----------
def set_session_cookies(resp: Response, settings: Settings, access: str, refresh: str, expires_in: int) -> None:
    common = {"secure": True, "path": "/"}
    resp.set_cookie(AT, access, max_age=expires_in, httponly=True, samesite="lax", **common)
    resp.set_cookie(RT, refresh, max_age=60 * 60 * 24 * 14, httponly=True, samesite="strict", **common)
    resp.set_cookie(CSRF, new_csrf_token(settings.csrf_secret), max_age=60 * 60 * 24 * 14,
                    httponly=False, samesite="strict", **common)


def clear_session_cookies(resp: Response) -> None:
    for name in (AT, RT, CSRF):
        resp.delete_cookie(name, path="/", secure=True)


def token_from_request(request: Request) -> str | None:
    """Единая точка извлечения токена для get_auth_context: Bearer (интеграции) -> cookie (браузер)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(AT)


# ---------- роуты ----------
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: SecretStr


async def _supabase_token(settings: Settings, grant: str, body: dict[str, str]) -> dict:
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/token"
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(url, params={"grant_type": grant}, json=body,
                         headers={"apikey": settings.supabase_anon_key})
    if r.status_code in (400, 401, 403):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")  # без деталей: нет oracle
    if r.status_code >= 500 or r.status_code == 429:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth provider unavailable")
    r.raise_for_status()
    return r.json()


@router.post("/login")
async def login(body: LoginIn, response: Response, settings: Annotated[Settings, Depends(get_settings)]):
    d = await _supabase_token(settings, "password",
                              {"email": body.email, "password": body.password.get_secret_value()})
    set_session_cookies(response, settings, d["access_token"], d["refresh_token"], int(d["expires_in"]))
    return {"success": True, "data": {"expires_in": d["expires_in"]}}  # токены в теле НЕ отдаём


@router.post("/refresh", dependencies=[Depends(require_csrf)])
async def refresh(request: Request, response: Response, settings: Annotated[Settings, Depends(get_settings)]):
    rt = request.cookies.get(RT)
    if not rt:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No session")
    d = await _supabase_token(settings, "refresh_token", {"refresh_token": rt})
    set_session_cookies(response, settings, d["access_token"], d["refresh_token"], int(d["expires_in"]))
    return {"success": True, "data": {"expires_in": d["expires_in"]}}


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(response: Response):
    clear_session_cookies(response)
    return {"success": True, "data": None}
