"""
Auth router для авторизации через Supabase
"""

from fastapi import APIRouter, HTTPException, Depends, Form, Header
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
import os
from supabase import create_client, Client
from datetime import datetime

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# OAuth2 scheme для извлечения токена из заголовка
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# Supabase клиент
def get_supabase_client() -> Client:
    """Получить Supabase клиент"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    
    if not supabase_url:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL not configured"
        )
    
    # Используем service role key для admin операций
    service_key = os.getenv("SUPABASE_SERVICE_KEY", supabase_key)
    
    return create_client(supabase_url, service_key)


# Pydantic модели
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    tenant_id: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    email: str
    tenant_id: Optional[str] = None
    created_at: datetime


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(user_data: UserRegister, supabase: Client = Depends(get_supabase_client)):
    """
    Регистрация нового пользователя через Supabase Auth
    """
    try:
        # Создаём пользователя в Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "tenant_id": user_data.tenant_id or "default-tenant"
                }
            }
        })
        
        if auth_response.user is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to create user. Email may already exist."
            )
        
        user = auth_response.user
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            tenant_id=user_data.tenant_id or "default-tenant",
            created_at=user.created_at or datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        if "already registered" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="User with this email already exists"
            )
        raise HTTPException(
            status_code=400,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    supabase: Client = Depends(get_supabase_client)
):
    """
    Авторизация пользователя (OAuth2 compatible)
    username = email
    """
    try:
        # Логин через Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": form_data.username,  # OAuth2 использует username
            "password": form_data.password
        })
        
        if auth_response.session is None:
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password"
            )
        
        session = auth_response.session
        
        return TokenResponse(
            access_token=session.access_token,
            token_type="bearer",
            expires_in=session.expires_in if hasattr(session, 'expires_in') else 3600,
            refresh_token=session.refresh_token if hasattr(session, 'refresh_token') else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/logout")
async def logout(supabase: Client = Depends(get_supabase_client)):
    """
    Выход из системы
    """
    try:
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Logout failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token: str = Depends(oauth2_scheme)
):
    """
    Получить информацию о текущем пользователе
    Требует Bearer токен в Authorization header
    """
    try:
        # Создаём Supabase клиент с токеном пользователя
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
        
        if not supabase_url:
            raise HTTPException(status_code=500, detail="SUPABASE_URL not configured")
        
        # Создаём клиент с user token вместо service key
        supabase = create_client(supabase_url, supabase_key)
        
        # Устанавливаем access token для текущей сессии
        supabase.auth.set_session(token, "")  # Устанавливаем access_token
        
        # Получаем пользователя
        user_response = supabase.auth.get_user(token)
        
        if user_response.user is None:
            raise HTTPException(
                status_code=401,
                detail="Not authenticated"
            )
        
        user = user_response.user
        
        # Получаем tenant_id из user metadata
        tenant_id = user.user_metadata.get("tenant_id", "default-tenant") if user.user_metadata else "default-tenant"
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            tenant_id=tenant_id,
            created_at=user.created_at.isoformat() if hasattr(user.created_at, 'isoformat') else str(user.created_at)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Failed to get user: {str(e)}"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    supabase: Client = Depends(get_supabase_client)
):
    """
    Обновить access token используя refresh token
    """
    try:
        auth_response = supabase.auth.refresh_session(refresh_token)
        
        if auth_response.session is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid refresh token"
            )
        
        session = auth_response.session
        
        return TokenResponse(
            access_token=session.access_token,
            token_type="bearer",
            expires_in=session.expires_in if hasattr(session, 'expires_in') else 3600,
            refresh_token=session.refresh_token if hasattr(session, 'refresh_token') else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Token refresh failed: {str(e)}"
        )
