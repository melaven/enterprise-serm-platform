"""
Репозиторий для работы с компаниями
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models.economics import Company
from ..exceptions import DatabaseError


class CompanyRepository(BaseRepository[Company]):
    """Репозиторий для управления данными компаний"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Company)
    
    async def get_by_name(self, name: str) -> Optional[Company]:
        """Найти компанию по названию"""
        try:
            query = select(Company).where(Company.name == name)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка поиска компании по названию", e)
    
    async def get_with_platforms(self, company_id: UUID) -> Optional[Company]:
        """Получить компанию со всеми платформами"""
        try:
            query = select(Company).options(
                selectinload(Company.platforms)
            ).where(Company.id == company_id)
            
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка получения компании с платформами", e)
    
    async def get_with_full_data(self, company_id: UUID) -> Optional[Company]:
        """Получить компанию со всеми связанными данными (платформы + отзывы)"""
        try:
            query = select(Company).options(
                selectinload(Company.platforms).selectinload(
                    Company.platforms.property.mapper.class_.reviews
                )
            ).where(Company.id == company_id)
            
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError("Ошибка получения компании с полными данными", e)
    
    async def search_by_name_pattern(self, pattern: str, limit: int = 10) -> List[Company]:
        """Поиск компаний по паттерну в названии"""
        try:
            query = select(Company).where(
                Company.name.ilike(f"%{pattern}%")
            ).limit(limit)
            
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise DatabaseError("Ошибка поиска компаний по паттерну", e)
    
    async def get_companies_with_metrics(self) -> List[Company]:
        """Получить все компании с базовыми экономическими метриками"""
        try:
            query = select(Company).options(
                selectinload(Company.platforms)
            )
            
            result = await self.db.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise DatabaseError("Ошибка получения компаний с метриками", e)
    
    async def update_economics(self, 
                              company_id: UUID, 
                              average_check: float = None,
                              margin_percent: float = None,
                              cac: float = None,
                              base_ltv: float = None) -> Company:
        """Обновить экономические показатели компании"""
        updates = {}
        if average_check is not None:
            updates['average_check'] = average_check
        if margin_percent is not None:
            updates['margin_percent'] = margin_percent
        if cac is not None:
            updates['cac'] = cac
        if base_ltv is not None:
            updates['base_ltv'] = base_ltv
        
        if not updates:
            # Если нечего обновлять, возвращаем текущую запись
            return await self.get_by_id_or_404(company_id)
        
        return await self.update(company_id, **updates)