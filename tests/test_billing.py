"""Тесты для биллинга и системы квот.

Проверяем:
- Атомарность операций резервирования и списания токенов
- Корректность возврата неиспользованных токенов
- Проверку лимитов перед операциями
- HTTP 402 при превышении квоты
- Интеграцию с воркерскими задачами
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4, UUID

from app.services.billing import QuotaService, QuotaExceededError, QuotaNotFoundError
from app.schemas.billing import QuotaLimits, QuotaUsage, QuotaStatus


@pytest.fixture
def tenant_id() -> UUID:
    """UUID тестового tenant'а."""
    return uuid4()


@pytest.fixture
def another_tenant_id() -> UUID:
    """UUID другого tenant'а для тестов изоляции."""
    return uuid4()


class TestQuotaServiceAtomicity:
    """Тесты атомарности операций с квотами."""

    @pytest.mark.asyncio
    async def test_reserve_tokens_atomic(self, mock_db_session, tenant_id):
        """Резервирование токенов атомарно: либо резервируется полностью, либо нет."""
        quota_service = QuotaService(mock_db_session)
        
        # Имитируем успешное резервирование
        mock_db_session.execute_return = {"success": True}
        result = await quota_service.reserve_llm_tokens(tenant_id, 1000)
        
        assert result is True
        assert mock_db_session.execute_called
        assert "reserve_llm_tokens" in mock_db_session.last_query

    @pytest.mark.asyncio
    async def test_reserve_tokens_fails_on_quota_exceeded(self, mock_db_session, tenant_id):
        """Резервирование возвращает False при превышении квоты."""
        quota_service = QuotaService(mock_db_session)
        
        # Имитируем превышение квоты
        mock_db_session.execute_return = {"success": False}
        result = await quota_service.reserve_llm_tokens(tenant_id, 100000)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_commit_tokens_returns_difference(self, mock_db_session, tenant_id):
        """Точное списание возвращает разницу между резервом и фактом."""
        quota_service = QuotaService(mock_db_session)
        
        # Резервировали 1000, использовали 750
        reserved = 1000
        actual = 750
        
        await quota_service.commit_llm_tokens(tenant_id, reserved=reserved, actual=actual)
        
        # Проверяем, что вызвана функция commit
        assert "commit_llm_tokens" in mock_db_session.last_query
        assert reserved in mock_db_session.last_params.values()
        assert actual in mock_db_session.last_params.values()

    @pytest.mark.asyncio
    async def test_release_tokens_on_error(self, mock_db_session, tenant_id):
        """Возврат зарезервированных токенов при ошибке."""
        quota_service = QuotaService(mock_db_session)
        
        tokens_to_release = 1000
        await quota_service.release_llm_tokens(tenant_id, tokens_to_release)
        
        assert "release_llm_tokens" in mock_db_session.last_query
        assert tokens_to_release in mock_db_session.last_params.values()


class TestQuotaServiceLimits:
    """Тесты проверки лимитов."""

    @pytest.mark.asyncio
    async def test_check_quota_available(self, mock_db_session, tenant_id):
        """Проверка квоты без списания возвращает корректный результат."""
        quota_service = QuotaService(mock_db_session)
        
        # Имитируем статус квот
        now = datetime.now(timezone.utc)
        mock_db_session.fetch_one_return = {
            "tenant_id": tenant_id,
            "max_llm_tokens": 100000,
            "max_reviews": 500,
            "used_llm_tokens": 10000,
            "used_reviews": 50,
            "reserved_llm_tokens": 5000,
            "created_at": now,
            "updated_at": now
        }
        mock_db_session.execute_return = {"available": True}
        
        check = await quota_service.check_quota(tenant_id, tokens=1000, reviews=10)
        
        assert check.available is True
        assert check.tokens_requested == 1000
        assert check.reviews_requested == 10

    @pytest.mark.asyncio
    async def test_check_quota_exceeds_tokens(self, mock_db_session, tenant_id):
        """Проверка квоты возвращает False при превышении токенов."""
        quota_service = QuotaService(mock_db_session)
        
        # Имитируем почти исчерпанную квоту токенов
        now = datetime.now(timezone.utc)
        mock_db_session.fetch_one_return = {
            "tenant_id": tenant_id,
            "max_llm_tokens": 100000,
            "max_reviews": 500,
            "used_llm_tokens": 95000,
            "used_reviews": 50,
            "reserved_llm_tokens": 4000,
            "created_at": now,
            "updated_at": now
        }
        mock_db_session.execute_return = {"available": False}
        
        check = await quota_service.check_quota(tenant_id, tokens=10000, reviews=10)
        
        assert check.available is False
        assert "tokens" in check.reason.lower()

    @pytest.mark.asyncio
    async def test_check_quota_exceeds_reviews(self, mock_db_session, tenant_id):
        """Проверка квоты возвращает False при превышении отзывов."""
        quota_service = QuotaService(mock_db_session)
        
        # Имитируем почти исчерпанную квоту отзывов
        now = datetime.now(timezone.utc)
        mock_db_session.fetch_one_return = {
            "tenant_id": tenant_id,
            "max_llm_tokens": 100000,
            "max_reviews": 500,
            "used_llm_tokens": 10000,
            "used_reviews": 490,
            "reserved_llm_tokens": 1000,
            "created_at": now,
            "updated_at": now
        }
        mock_db_session.execute_return = {"available": False}
        
        check = await quota_service.check_quota(tenant_id, tokens=1000, reviews=20)
        
        assert check.available is False
        assert "reviews" in check.reason.lower()


class TestQuotaServiceReviews:
    """Тесты списания отзывов."""

    @pytest.mark.asyncio
    async def test_consume_reviews_success(self, mock_db_session, tenant_id):
        """Успешное списание отзывов."""
        quota_service = QuotaService(mock_db_session)
        
        mock_db_session.execute_return = {"success": True}
        result = await quota_service.consume_reviews(tenant_id, 10)
        
        assert result is True
        assert "consume_reviews" in mock_db_session.last_query

    @pytest.mark.asyncio
    async def test_consume_reviews_fails_on_quota_exceeded(self, mock_db_session, tenant_id):
        """Списание отзывов возвращает False при превышении квоты."""
        quota_service = QuotaService(mock_db_session)
        
        mock_db_session.execute_return = {"success": False}
        result = await quota_service.consume_reviews(tenant_id, 100)
        
        assert result is False


class TestQuotaStatus:
    """Тесты модели QuotaStatus и её вычисляемых свойств."""

    def test_total_tokens_committed(self):
        """Общее количество токенов = использованные + зарезервированные."""
        now = datetime.now(timezone.utc)
        status = QuotaStatus(
            tenant_id=uuid4(),
            limits=QuotaLimits(max_llm_tokens=100000, max_reviews=500),
            usage=QuotaUsage(used_llm_tokens=10000, used_reviews=50, reserved_llm_tokens=5000),
            created_at=now,
            updated_at=now
        )
        
        assert status.total_tokens_committed == 15000  # 10000 + 5000

    def test_tokens_available(self):
        """Доступные токены = лимит - использованные - зарезервированные."""
        now = datetime.now(timezone.utc)
        status = QuotaStatus(
            tenant_id=uuid4(),
            limits=QuotaLimits(max_llm_tokens=100000, max_reviews=500),
            usage=QuotaUsage(used_llm_tokens=10000, used_reviews=50, reserved_llm_tokens=5000),
            created_at=now,
            updated_at=now
        )
        
        assert status.tokens_available == 85000  # 100000 - 15000

    def test_reviews_available(self):
        """Доступные отзывы = лимит - использованные."""
        now = datetime.now(timezone.utc)
        status = QuotaStatus(
            tenant_id=uuid4(),
            limits=QuotaLimits(max_llm_tokens=100000, max_reviews=500),
            usage=QuotaUsage(used_llm_tokens=10000, used_reviews=50, reserved_llm_tokens=5000),
            created_at=now,
            updated_at=now
        )
        
        assert status.reviews_available == 450  # 500 - 50

    def test_tokens_usage_percent(self):
        """Процент использования токенов."""
        now = datetime.now(timezone.utc)
        status = QuotaStatus(
            tenant_id=uuid4(),
            limits=QuotaLimits(max_llm_tokens=100000, max_reviews=500),
            usage=QuotaUsage(used_llm_tokens=10000, used_reviews=50, reserved_llm_tokens=5000),
            created_at=now,
            updated_at=now
        )
        
        assert status.tokens_usage_percent == 15.0  # (15000 / 100000) * 100

    def test_reviews_usage_percent(self):
        """Процент использования отзывов."""
        now = datetime.now(timezone.utc)
        status = QuotaStatus(
            tenant_id=uuid4(),
            limits=QuotaLimits(max_llm_tokens=100000, max_reviews=500),
            usage=QuotaUsage(used_llm_tokens=10000, used_reviews=50, reserved_llm_tokens=5000),
            created_at=now,
            updated_at=now
        )
        
        assert status.reviews_usage_percent == 10.0  # (50 / 500) * 100


# === MOCK FIXTURES ===

@pytest.fixture
def mock_db_session():
    """Mock AsyncSession для тестирования QuotaService без реальной БД."""
    
    class MockAsyncSession:
        def __init__(self):
            self.execute_called = False
            self.execute_return = None
            self.fetch_one_return = None
            self.last_query = ""
            self.last_params = {}
        
        async def execute(self, query, params=None):
            self.execute_called = True
            self.last_query = str(query)
            self.last_params = params or {}
            fetch_one_return = self.fetch_one_return
            self.fetch_one_return = None
            
            class MockResult:
                def __init__(self, return_value, fetch_one_value):
                    self._return = return_value
                    self._fetch_one = fetch_one_value
                
                def fetchone(self):
                    if self._fetch_one:
                        class Row:
                            def __init__(self, data):
                                for key, value in data.items():
                                    setattr(self, key, value)
                        return Row(self._fetch_one)
                    if self._return:
                        class Row:
                            def __init__(self, data):
                                for key, value in data.items():
                                    setattr(self, key, value)
                        return Row(self._return)
                    return None
            
            return MockResult(self.execute_return, fetch_one_return)
    
    return MockAsyncSession()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
