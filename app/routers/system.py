"""
Системные роутеры для тестирования и диагностики
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import (
    NotFoundError,
    AccessDeniedError,
    ValidationError,
    DatabaseError,
    DatabaseTimeoutError,
    LLMServiceError,
    EconomicsCalculationError
)

router = APIRouter()


@router.get("/test-errors", tags=["System Tests"])
async def test_error_handlers(
    error_type: str = Query(
        ...,
        description="Тип ошибки для тестирования",
        regex="^(404|403|validation|db|timeout|llm|calculation|unknown)$"
    ),
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint для тестирования различных типов ошибок
    
    Доступные типы:
    - 404: NotFoundError
    - 403: AccessDeniedError  
    - validation: ValidationError
    - db: DatabaseError
    - timeout: DatabaseTimeoutError
    - llm: LLMServiceError
    - calculation: EconomicsCalculationError
    - unknown: Неизвестная ошибка
    """
    
    if error_type == "404":
        raise NotFoundError("Компания", "test-company-123")
    
    elif error_type == "403":
        raise AccessDeniedError("Недостаточно прав для просмотра финансовых данных")
    
    elif error_type == "validation":
        raise ValidationError("rating", 6, "Рейтинг должен быть от 1 до 5")
    
    elif error_type == "db":
        raise DatabaseError("Ошибка подключения к Supabase")
    
    elif error_type == "timeout":
        raise DatabaseTimeoutError("запроса статистики отзывов")
    
    elif error_type == "llm":
        raise LLMServiceError("OpenAI API недоступен")
    
    elif error_type == "calculation":
        raise EconomicsCalculationError("LTV", "отрицательное значение CAC")
    
    elif error_type == "unknown":
        # Имитация неожиданной ошибки
        raise RuntimeError("Это неожиданная системная ошибка")
    
    return {"message": "Все обработчики ошибок работают корректно!"}