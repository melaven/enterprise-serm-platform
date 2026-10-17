"""JWT-аутентификация: Bearer-токен -> JWTPayload -> tenant_id.

Поддержка алгоритмов:
- HS256: используется для legacy JWT с SUPABASE_JWT_SECRET
- ES256: используется Supabase Auth для новых токенов (требует JWKS)
- RS256: поддержка для future-proof интеграций
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from pydantic import ValidationError

from app.schemas.auth import JWTPayload

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthConfig:
    secret: str | None
    jwks_url: str | None
    audience: str = "authenticated"
    algorithms: tuple[str, ...] = (
        "HS256",
        "ES256",  # Supabase использует ES256 для JWT токенов
        "RS256",  # Также поддержка RS256 на будущее
    )
    leeway_s: int = 10  # допуск на расхождение часов


@lru_cache
def get_auth_config() -> AuthConfig:
    """Секрет берётся из настроек (SUPABASE_JWT_SECRET). Дефолта в коде нет:
    без секрета запрос падает (fail-closed), а не принимает «тестовый» токен.
    В тестах подменяется через app.dependency_overrides[get_auth_config]."""
    from app.core.config import get_settings  # локальный импорт: проще мокать

    settings = get_settings()

    # Для Supabase ES256: используем JWKS endpoint
    supabase_url = os.getenv("SUPABASE_URL")
    jwks_url = None
    if supabase_url:
        # JWKS endpoint для Supabase (публичный): https://<project>.supabase.co/auth/v1/.well-known/jwks.json
        jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"

    # Для HS256: используем JWT secret
    secret = settings.supabase_jwt_secret

    # Требуем хотя бы один способ валидации
    if not secret and not jwks_url:
        raise RuntimeError(
            "Either SUPABASE_JWT_SECRET or SUPABASE_URL must be configured"
        )

    return AuthConfig(secret=secret, jwks_url=jwks_url, audience=settings.jwt_audience)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_token(token: str, config: AuthConfig) -> JWTPayload:
    """Проверяет подпись, exp, aud и разбирает claim'ы.

    Поддерживает оба метода валидации:
    - HS256: использует secret напрямую
    - ES256/RS256: использует JWKS для получения публичного ключа

    Raises:
        jwt.PyJWTError: подпись/срок/аудитория неверны (-> 401)
        pydantic.ValidationError: нет валидных sub/tenant_id (-> 403)
    """
    # Сначала декодируем header чтобы узнать алгоритм
    unverified_header = jwt.get_unverified_header(token)
    algorithm = unverified_header.get("alg", "HS256")

    # Выбираем метод валидации в зависимости от алгоритма
    if algorithm == "HS256" and config.secret:
        # HS256: используем secret напрямую
        signing_key = config.secret
    elif algorithm in ("ES256", "RS256") and config.jwks_url:
        # ES256/RS256: получаем публичный ключ из JWKS
        try:
            jwks_client = PyJWKClient(config.jwks_url)
            signing_key_obj = jwks_client.get_signing_key_from_jwt(token)
            signing_key = signing_key_obj.key
        except Exception as e:
            raise jwt.PyJWTError(f"Failed to fetch JWKS signing key: {str(e)}")
    else:
        raise jwt.PyJWTError(
            f"Unsupported algorithm {algorithm} or missing configuration"
        )

    # Валидируем токен
    claims = jwt.decode(
        token,
        signing_key,
        algorithms=list(config.algorithms),
        audience=config.audience,
        leeway=config.leeway_s,
        options={"require": ["exp", "sub", "aud"]},
    )
    return JWTPayload.model_validate(claims)


async def get_jwt_payload(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    config: Annotated[AuthConfig, Depends(get_auth_config)],
) -> JWTPayload:
    if creds is None:
        raise _unauthorized("Missing bearer token")
    try:
        return decode_token(creds.credentials, config)
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc
    except ValidationError as exc:
        # токен подлинный, но к арендатору не привязан
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is not bound to a tenant",
        ) from exc


async def get_current_tenant(
    payload: Annotated[JWTPayload, Depends(get_jwt_payload)],
) -> UUID:
    """Извлекает tenant_id из JWT payload.

    Если tenant_id отсутствует в токене, используем sub (user_id) как tenant_id.
    Это позволяет работать с токенами Supabase без custom claims.
    """
    return payload.tenant_id or payload.sub


CurrentPayload = Annotated[JWTPayload, Depends(get_jwt_payload)]
CurrentTenant = Annotated[UUID, Depends(get_current_tenant)]
