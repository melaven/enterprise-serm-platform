import logging
import os
import secrets

from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.infrastructure.persistence.models.economics import Company, Platform, Review
from app.infrastructure.persistence.models.review_reply import ReviewReply

logger = logging.getLogger(__name__)


class AdminAuthenticationBackend(AuthenticationBackend):
    """Protect SQLAdmin with credentials configured outside the application."""

    def __init__(self) -> None:
        is_production = os.getenv("ENVIRONMENT", "development").lower() in {
            "prod",
            "production",
        }
        secret_key = os.getenv("ADMIN_SECRET_KEY")
        if not secret_key:
            if is_production:
                raise RuntimeError("ADMIN_SECRET_KEY must be configured in production")
            secret_key = secrets.token_urlsafe(32)
            logger.warning(
                "ADMIN_SECRET_KEY is not configured; admin sessions will reset on restart"
            )
        if is_production and not (
            os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD")
        ):
            raise RuntimeError(
                "ADMIN_USERNAME and ADMIN_PASSWORD must be configured in production"
            )
        if not (os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD")):
            logger.warning(
                "SQLAdmin login is disabled until ADMIN_USERNAME and ADMIN_PASSWORD are configured"
            )
        super().__init__(secret_key=secret_key)

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = os.getenv("ADMIN_USERNAME")
        password = os.getenv("ADMIN_PASSWORD")
        submitted_username = str(form.get("username", ""))
        submitted_password = str(form.get("password", ""))

        if not username or not password:
            return False

        username_matches = secrets.compare_digest(
            submitted_username.encode(), username.encode()
        )
        password_matches = secrets.compare_digest(
            submitted_password.encode(), password.encode()
        )
        if not (username_matches and password_matches):
            return False

        request.session.update({"admin": username})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return bool(request.session.get("admin"))


class CompanyAdmin(ModelView, model=Company):
    name = "Тенант"
    name_plural = "Тенанты"
    column_list = [
        Company.id,
        Company.name,
        Company.notification_email,
        Company.created_at,
    ]
    column_searchable_list = [Company.name, Company.notification_email]


class PlatformAdmin(ModelView, model=Platform):
    name = "Платформа"
    name_plural = "Платформы"
    column_list = [
        Platform.id,
        Platform.company_id,
        Platform.name,
        Platform.platform_url,
        Platform.average_rating,
    ]
    column_searchable_list = [Platform.name]


class ReviewAdmin(ModelView, model=Review):
    name = "Отзыв"
    name_plural = "Отзывы"
    column_list = [
        Review.id,
        Review.company_id,
        Review.platform_id,
        Review.moderation_status,
        Review.rating,
    ]
    column_details_list = [
        Review.id,
        Review.company_id,
        Review.platform_id,
        Review.moderation_status,
        Review.rating,
        Review.text,
        Review.si_response,
        Review.suggested_reply,
        Review.auto_reply,
        Review.ai_error,
        Review.dlq_reason,
        Review.created_at,
        Review.updated_at,
    ]


class ReviewReplyAdmin(ModelView, model=ReviewReply):
    name = "Ответ на отзыв"
    name_plural = "Ответы на отзывы"
    column_list = [
        ReviewReply.review_id,
        ReviewReply.company_id,
        ReviewReply.created_at,
        ReviewReply.updated_at,
    ]
    column_details_list = [
        ReviewReply.review_id,
        ReviewReply.company_id,
        ReviewReply.reply_text,
        ReviewReply.created_at,
        ReviewReply.updated_at,
    ]
