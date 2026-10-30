"""
Базовый абстрактный репозиторий
"""

from abc import ABC
from typing import Any, Generic, Protocol, TypeVar
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DatabaseError, NotFoundError


class HasId(Protocol):
    id: Any


T = TypeVar("T", bound=HasId)


class BaseRepository(Generic[T], ABC):
    """Базовый репозиторий с CRUD операциями"""

    def __init__(self, db: AsyncSession, model: type[T]):
        self.db = db
        self.model = model

    async def create(self, **kwargs) -> T:
        """Создать новую запись"""
        try:
            instance = self.model(**kwargs)
            self.db.add(instance)
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Ошибка создания {self.model.__name__}", e)

    async def get_by_id(self, id: UUID, relations: list[str] | None = None) -> T | None:
        """Получить запись по ID"""
        try:
            query = select(self.model).where(self.model.id == id)

            # Подключаем связанные данные если указаны
            if relations:
                for relation in relations:
                    query = query.options(selectinload(getattr(self.model, relation)))

            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Ошибка получения {self.model.__name__} по ID", e)

    async def get_by_id_or_404(self, id: UUID, relations: list[str] | None = None) -> T:
        """Получить запись по ID или выбросить 404"""
        instance = await self.get_by_id(id, relations)
        if not instance:
            raise NotFoundError(self.model.__name__, str(id))
        return instance

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        relations: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[T]:
        """Получить все записи с пагинацией и фильтрами"""
        try:
            query = select(self.model)

            # Применяем фильтры
            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)

            # Подключаем связанные данные
            if relations:
                for relation in relations:
                    query = query.options(selectinload(getattr(self.model, relation)))

            query = query.limit(limit).offset(offset)
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Ошибка получения списка {self.model.__name__}", e)

    async def update(self, id: UUID, **kwargs) -> T:
        """Обновить запись по ID"""
        try:
            # Проверяем существование записи
            await self.get_by_id_or_404(id)

            # Обновляем поля
            query = update(self.model).where(self.model.id == id).values(**kwargs)
            await self.db.execute(query)
            await self.db.commit()

            # Возвращаем обновленную запись
            updated = await self.get_by_id(id)
            if updated is None:
                raise NotFoundError(self.model.__name__, str(id))
            return updated
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Ошибка обновления {self.model.__name__}", e)

    async def delete(self, id: UUID) -> bool:
        """Удалить запись по ID"""
        try:
            # Проверяем существование записи
            await self.get_by_id_or_404(id)

            query = delete(self.model).where(self.model.id == id)
            result = await self.db.execute(query)
            await self.db.commit()

            return getattr(result, "rowcount", 0) > 0
        except Exception as e:
            await self.db.rollback()
            raise DatabaseError(f"Ошибка удаления {self.model.__name__}", e)

    async def exists(self, id: UUID) -> bool:
        """Проверить существование записи"""
        try:
            query = select(self.model.id).where(self.model.id == id)
            result = await self.db.execute(query)
            return result.scalar_one_or_none() is not None
        except Exception as e:
            raise DatabaseError(
                f"Ошибка проверки существования {self.model.__name__}", e
            )

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Подсчет записей с фильтрами"""
        try:
            from sqlalchemy import func

            query = select(func.count(self.model.id))

            if filters:
                for field, value in filters.items():
                    if hasattr(self.model, field):
                        query = query.where(getattr(self.model, field) == value)

            result = await self.db.execute(query)
            return result.scalar() or 0
        except Exception as e:
            raise DatabaseError(f"Ошибка подсчета {self.model.__name__}", e)
