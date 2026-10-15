"""
JWT Token Handler для мультитенантной аутентификации
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

import jwt
import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class AuthSettings(BaseSettings):
    """Настройки аутентификации"""
    
    # JWT настройки
    jwt_secret: Optional[str] = None  # Для legacy HS256
    jwt_algorithm: str = "RS256"      # RS256 для JWKS или HS256 для legacy
    
    # JWKS настройки  
    jwks_url: Optional[str] = None
    jwks_cache_ttl: int = 3600  # TTL кэша JWKS в секундах
    
    # Supabase настройки
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    
    class Config:
        env_prefix = "AUTH_"


class AuthContext(BaseModel):
    """Контекст аутентификации пользователя"""
    
    user_id: UUID = Field(..., description="ID пользователя из JWT")
    company_id: UUID = Field(..., description="ID компании (tenant) из JWT") 
    email: Optional[str] = Field(None, description="Email пользователя")
    role: Optional[str] = Field(None, description="Роль пользователя")
    
    # Дополнительные claims из JWT
    claims: Dict[str, Any] = Field(default_factory=dict)


class JWTHandler:
    """Обработчик JWT токенов с поддержкой JWKS и legacy режима"""
    
    def __init__(self, settings: AuthSettings = None):
        self.settings = settings or AuthSettings()
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_expires: Optional[int] = None
        
        # Валидация настроек
        if self.settings.jwt_algorithm == "RS256" and not self.settings.jwks_url:
            raise ValueError("JWKS URL required for RS256 algorithm")
        
        if self.settings.jwt_algorithm == "HS256" and not self.settings.jwt_secret:
            raise ValueError("JWT secret required for HS256 algorithm")
    
    async def verify_token(self, token: str) -> AuthContext:
        """
        Проверка JWT токена и извлечение контекста аутентификации
        """
        try:
            # Декодируем заголовок для получения kid (key id)
            unverified_header = jwt.get_unverified_header(token)
            
            if self.settings.jwt_algorithm == "RS256":
                # Получаем публичный ключ из JWKS
                public_key = await self._get_public_key(unverified_header.get("kid"))
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    options={"verify_exp": True, "verify_aud": False}
                )
            else:
                # Legacy режим с HS256
                payload = jwt.decode(
                    token,
                    self.settings.jwt_secret,
                    algorithms=["HS256"],
                    options={"verify_exp": True, "verify_aud": False}
                )
            
            # Извлекаем обязательные поля
            user_id = self._extract_user_id(payload)
            company_id = self._extract_company_id(payload)
            
            if not user_id or not company_id:
                raise ValueError("Missing required claims: user_id or company_id")
            
            return AuthContext(
                user_id=UUID(user_id),
                company_id=UUID(company_id),
                email=payload.get("email"),
                role=payload.get("role", "user"),
                claims=payload
            )
            
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise ValueError(f"Token verification failed: {str(e)}")
    
    def _extract_user_id(self, payload: Dict[str, Any]) -> Optional[str]:
        """Извлечение user_id из различных возможных полей JWT"""
        
        # Стандартные поля
        if "sub" in payload:
            return payload["sub"]
        
        # Supabase поля  
        if "user_id" in payload:
            return payload["user_id"]
        
        # Кастомные поля
        if "uid" in payload:
            return payload["uid"]
        
        return None
    
    def _extract_company_id(self, payload: Dict[str, Any]) -> Optional[str]:
        """Извлечение company_id из JWT claims"""
        
        # Прямое поле company_id
        if "company_id" in payload:
            return payload["company_id"]
        
        # Из app_metadata (Supabase)
        app_metadata = payload.get("app_metadata", {})
        if "company_id" in app_metadata:
            return app_metadata["company_id"]
        
        # Из user_metadata
        user_metadata = payload.get("user_metadata", {})
        if "company_id" in user_metadata:
            return user_metadata["company_id"]
        
        # Из кастомного claim tenant_id
        if "tenant_id" in payload:
            return payload["tenant_id"]
        
        return None
    
    async def _get_public_key(self, kid: Optional[str]) -> str:
        """Получение публичного ключа из JWKS endpoint"""
        
        if not self.settings.jwks_url:
            raise ValueError("JWKS URL not configured")
        
        # Проверяем кэш
        import time
        now = int(time.time())
        
        if (self._jwks_cache and self._jwks_cache_expires and 
            now < self._jwks_cache_expires):
            jwks_data = self._jwks_cache
        else:
            # Загружаем JWKS
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        self.settings.jwks_url,
                        timeout=10.0
                    )
                    response.raise_for_status()
                    jwks_data = response.json()
                    
                    # Кэшируем
                    self._jwks_cache = jwks_data
                    self._jwks_cache_expires = now + self.settings.jwks_cache_ttl
                    
                except httpx.RequestError as e:
                    raise ValueError(f"Failed to fetch JWKS: {str(e)}")
        
        # Ищем ключ по kid
        for key in jwks_data.get("keys", []):
            if key.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(key)
        
        # Если kid не найден, берем первый RS256 ключ
        for key in jwks_data.get("keys", []):
            if key.get("alg") == "RS256":
                return jwt.algorithms.RSAAlgorithm.from_jwk(key)
        
        raise ValueError(f"No suitable key found in JWKS for kid: {kid}")


# Глобальный экземпляр JWT handler
_jwt_handler: Optional[JWTHandler] = None

def get_jwt_handler() -> JWTHandler:
    """Получить глобальный экземпляр JWT handler"""
    global _jwt_handler
    
    if _jwt_handler is None:
        _jwt_handler = JWTHandler()
    
    return _jwt_handler