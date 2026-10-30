"""JWT-токен схемы для multi-tenant аутентификации."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JWTPayload(BaseModel):
    """Payload JWT токена с tenant_id для multi-tenant изоляции."""

    model_config = ConfigDict(
        frozen=True, extra="ignore"
    )  # Изменено с "forbid" на "ignore"

    sub: UUID = Field(description="User ID из Supabase Auth")
    tenant_id: UUID | None = Field(
        default=None, description="Company ID для RLS изоляции"
    )
    company_id: UUID | None = Field(
        default=None, description="Company ID для RLS изоляции"
    )

    # Дополнительные поля из Supabase JWT
    aud: str = Field(default="authenticated", description="JWT audience")
    exp: int | None = Field(default=None, description="Token expiration timestamp")
    iat: int | None = Field(default=None, description="Token issued at timestamp")
    iss: str | None = Field(default=None, description="Token issuer")

    # Company role из custom access token hook
    company_role: str | None = Field(default=None, description="User role in company")


class AuthContext(BaseModel):
    """Контекст аутентифицированного пользователя."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    company_id: UUID
    company_role: str | None = None
