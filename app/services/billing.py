"""Сервис управления квотами для мультитенантной системы.

QuotaService обеспечивает атомарные операции резервирования, списания и возврата
токенов/отзывов через PostgreSQL транзакции и SQL функции.

Пайплайн учета токенов:
1. reserve_llm_tokens() - оценочное резервирование перед LLM запросом
2. LLM запрос -> получение usage_metadata.total_token_count
3. commit_llm_tokens() - точное списание + возврат разницы
4. release_llm_tokens() - полный возврат при ошибке (fallback)

Пример использования:
    quota_service = QuotaService(db_session)
    
    # Проверка перед запуском задачи
    check = await quota_service.check_quota(tenant_id, tokens=5000, reviews=10)
    if not check.available:
        raise HTTPException(402, detail=check.reason)
    
    # Резервирование токенов перед LLM
    if not await quota_service.reserve_llm_tokens(tenant_id, 5000):
        raise QuotaExceededError("Cannot reserve tokens")
    
    try:
        # LLM запрос
        result, actual_tokens = await llm.analyze(...)
        
        # Точное списание
        await quota_service.commit_llm_tokens(tenant_id, reserved=5000, actual=actual_tokens)
    except Exception:
        # Возврат при ошибке
        await quota_service.release_llm_tokens(tenant_id, 5000)
        raise
"""

from uuid import UUID

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.billing import (
    QuotaCheck,
    QuotaLimits,
    QuotaStatus,
    QuotaUsage,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class QuotaExceededError(Exception):
    """Превышение квоты: нельзя выполнить операцию."""

    def __init__(
        self,
        message: str,
        *,
        tenant_id: UUID,
        requested: dict[str, int],
        available: dict[str, int],
    ) -> None:
        super().__init__(message)
        self.tenant_id = tenant_id
        self.requested = requested
        self.available = available


class QuotaNotFoundError(Exception):
    """Квота для tenant'а не найдена (не инициализирована)."""

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__(f"Quota not found for tenant {tenant_id}")
        self.tenant_id = tenant_id


class QuotaService:
    """Сервис для атомарного управления квотами через PostgreSQL функции."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Args:
            session: AsyncSession с RLS контекстом для tenant изоляции
        """
        self._session = session

    async def get_status(self, tenant_id: UUID) -> QuotaStatus:
        """Получить текущий статус квот tenant'а.

        Args:
            tenant_id: UUID компании

        Returns:
            QuotaStatus с лимитами и использованием

        Raises:
            QuotaNotFoundError: Если квота не найдена
        """
        query = text(
            """
            SELECT 
                tenant_id,
                max_llm_tokens,
                max_reviews,
                used_llm_tokens,
                used_reviews,
                reserved_llm_tokens,
                created_at,
                updated_at
            FROM tenant_quotas
            WHERE tenant_id = :tenant_id
            """
        )

        result = await self._session.execute(query, {"tenant_id": str(tenant_id)})
        row = result.fetchone()

        if row is None:
            raise QuotaNotFoundError(tenant_id)

        return QuotaStatus(
            tenant_id=row.tenant_id,
            limits=QuotaLimits(
                max_llm_tokens=row.max_llm_tokens,
                max_reviews=row.max_reviews,
            ),
            usage=QuotaUsage(
                used_llm_tokens=row.used_llm_tokens,
                used_reviews=row.used_reviews,
                reserved_llm_tokens=row.reserved_llm_tokens,
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def check_quota(
        self,
        tenant_id: UUID,
        *,
        tokens: int = 0,
        reviews: int = 0,
    ) -> QuotaCheck:
        """Проверить доступность квоты БЕЗ списания.

        Использует SQL функцию check_quota_available() для атомарной проверки.

        Args:
            tenant_id: UUID компании
            tokens: Сколько токенов нужно проверить
            reviews: Сколько отзывов нужно проверить

        Returns:
            QuotaCheck с результатом проверки
        """
        try:
            status = await self.get_status(tenant_id)
        except QuotaNotFoundError:
            logger.error(
                "quota_check_failed_not_found",
                tenant_id=str(tenant_id),
            )
            return QuotaCheck(
                available=False,
                reason=f"Quota not initialized for tenant {tenant_id}",
                tokens_requested=tokens,
                reviews_requested=reviews,
                tokens_available=0,
                reviews_available=0,
            )

        # Вызываем SQL функцию для проверки
        query = text(
            "SELECT check_quota_available(:tenant_id, :tokens, :reviews) AS available"
        )
        result = await self._session.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "tokens": tokens,
                "reviews": reviews,
            },
        )
        row = result.fetchone()
        available = row.available if row else False

        tokens_available = status.tokens_available
        reviews_available = status.reviews_available

        reason = None
        if not available:
            issues = []
            if tokens > 0 and tokens > tokens_available:
                issues.append(
                    f"tokens: requested {tokens}, available {tokens_available}"
                )
            if reviews > 0 and reviews > reviews_available:
                issues.append(
                    f"reviews: requested {reviews}, available {reviews_available}"
                )
            reason = "Quota exceeded: " + "; ".join(issues)

        logger.info(
            "quota_check",
            tenant_id=str(tenant_id),
            available=available,
            tokens_requested=tokens,
            reviews_requested=reviews,
            tokens_available=tokens_available,
            reviews_available=reviews_available,
        )

        return QuotaCheck(
            available=available,
            reason=reason,
            tokens_requested=tokens,
            reviews_requested=reviews,
            tokens_available=tokens_available,
            reviews_available=reviews_available,
        )

    async def reserve_llm_tokens(self, tenant_id: UUID, tokens: int) -> bool:
        """Зарезервировать токены (оценочное списание перед LLM запросом).

        Использует SQL функцию reserve_llm_tokens() для атомарного резервирования.

        Args:
            tenant_id: UUID компании
            tokens: Количество токенов для резервирования (оценка)

        Returns:
            True если резервирование успешно, False если квота превышена

        Raises:
            QuotaNotFoundError: Если квота не найдена
        """
        query = text("SELECT reserve_llm_tokens(:tenant_id, :tokens) AS success")
        result = await self._session.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "tokens": tokens,
            },
        )
        row = result.fetchone()
        success = row.success if row else False

        if success:
            logger.info(
                "tokens_reserved",
                tenant_id=str(tenant_id),
                tokens=tokens,
            )
        else:
            logger.warning(
                "tokens_reservation_failed",
                tenant_id=str(tenant_id),
                tokens=tokens,
            )

        return success

    async def commit_llm_tokens(
        self,
        tenant_id: UUID,
        *,
        reserved: int,
        actual: int,
    ) -> None:
        """Списать фактические токены и вернуть разницу с резервом.

        Использует SQL функцию commit_llm_tokens() для атомарного списания.

        Args:
            tenant_id: UUID компании
            reserved: Количество зарезервированных токенов
            actual: Фактически использованные токены (из usage_metadata)

        Raises:
            QuotaNotFoundError: Если квота не найдена
        """
        query = text(
            "SELECT commit_llm_tokens(:tenant_id, :reserved, :actual) AS result"
        )

        try:
            await self._session.execute(
                query,
                {
                    "tenant_id": str(tenant_id),
                    "reserved": reserved,
                    "actual": actual,
                },
            )

            returned = max(0, reserved - actual)
            logger.info(
                "tokens_committed",
                tenant_id=str(tenant_id),
                reserved=reserved,
                actual=actual,
                returned=returned,
            )

        except Exception as e:
            logger.error(
                "tokens_commit_failed",
                tenant_id=str(tenant_id),
                reserved=reserved,
                actual=actual,
                error=str(e),
            )
            raise

    async def release_llm_tokens(self, tenant_id: UUID, tokens: int) -> None:
        """Вернуть зарезервированные токены (при ошибке или отмене).

        Использует SQL функцию release_llm_tokens() для атомарного возврата.

        Args:
            tenant_id: UUID компании
            tokens: Количество токенов для возврата

        Raises:
            QuotaNotFoundError: Если квота не найдена
        """
        query = text("SELECT release_llm_tokens(:tenant_id, :tokens) AS result")

        try:
            await self._session.execute(
                query,
                {
                    "tenant_id": str(tenant_id),
                    "tokens": tokens,
                },
            )

            logger.info(
                "tokens_released",
                tenant_id=str(tenant_id),
                tokens=tokens,
            )

        except Exception as e:
            logger.error(
                "tokens_release_failed",
                tenant_id=str(tenant_id),
                tokens=tokens,
                error=str(e),
            )
            raise

    async def consume_reviews(self, tenant_id: UUID, count: int) -> bool:
        """Списать отзывы после успешного сохранения.

        Использует SQL функцию consume_reviews() для атомарного списания.

        Args:
            tenant_id: UUID компании
            count: Количество обработанных отзывов

        Returns:
            True если списание успешно, False если квота превышена

        Raises:
            QuotaNotFoundError: Если квота не найдена
        """
        query = text("SELECT consume_reviews(:tenant_id, :count) AS success")
        result = await self._session.execute(
            query,
            {
                "tenant_id": str(tenant_id),
                "count": count,
            },
        )
        row = result.fetchone()
        success = row.success if row else False

        if success:
            logger.info(
                "reviews_consumed",
                tenant_id=str(tenant_id),
                count=count,
            )
        else:
            logger.warning(
                "reviews_consumption_failed",
                tenant_id=str(tenant_id),
                count=count,
            )

        return success

    async def update_limits(
        self,
        tenant_id: UUID,
        *,
        max_llm_tokens: int | None = None,
        max_reviews: int | None = None,
    ) -> QuotaStatus:
        """Обновить лимиты квот (только для администратора).

        Args:
            tenant_id: UUID компании
            max_llm_tokens: Новый лимит токенов (если нужно изменить)
            max_reviews: Новый лимит отзывов (если нужно изменить)

        Returns:
            QuotaStatus с обновленными лимитами

        Raises:
            QuotaNotFoundError: Если квота не найдена
            ValueError: Если не указано ни одного лимита
        """
        if max_llm_tokens is None and max_reviews is None:
            raise ValueError("At least one limit must be specified")

        updates = []
        params: dict[str, str | int] = {"tenant_id": str(tenant_id)}

        if max_llm_tokens is not None:
            updates.append("max_llm_tokens = :max_llm_tokens")
            params["max_llm_tokens"] = max_llm_tokens

        if max_reviews is not None:
            updates.append("max_reviews = :max_reviews")
            params["max_reviews"] = max_reviews

        query = text(
            f"""
            UPDATE tenant_quotas
            SET {", ".join(updates)}
            WHERE tenant_id = :tenant_id
            RETURNING tenant_id
            """
        )

        result = await self._session.execute(query, params)
        row = result.fetchone()

        if row is None:
            raise QuotaNotFoundError(tenant_id)

        logger.info(
            "quota_limits_updated",
            tenant_id=str(tenant_id),
            max_llm_tokens=max_llm_tokens,
            max_reviews=max_reviews,
        )

        return await self.get_status(tenant_id)


# Экспорт для удобного импорта
__all__ = [
    "QuotaService",
    "QuotaExceededError",
    "QuotaNotFoundError",
]
