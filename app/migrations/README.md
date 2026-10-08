# Миграции базы данных SERM

## Объединение моделей отзывов

В рамках рефакторинга архитектуры были объединены дублирующиеся модели данных для отзывов:

### Было:
- `Review` (основная модель в `app/models/economics.py`) 
- `LNRReviewLog` (устаревшая модель в `app/database.py`)

### Стало:
- Единая модель `Review` с дополнительным полем `external_review_id`

## Изменения в модели Review

Добавлено поле:
```python
external_review_id: Mapped[str | None] = mapped_column(
    String(255), nullable=True, unique=True, index=True
)
```

Это поле предназначено для:
- Хранения ID отзывов из внешних систем (Google Maps, 2GIS, Trustpilot)
- Предотвращения дубликатов при импорте
- Синхронизации с внешними API

## Запуск миграции

```bash
# Перейти в папку проекта
cd app

# Запустить миграцию
python migrations/run_migration.py
```

## Что делает миграция

1. ✅ Добавляет поле `external_review_id VARCHAR(255)` в таблицу `reviews`
2. ✅ Создает уникальный индекс для быстрого поиска
3. ✅ Удаляет устаревшую таблицу `lnr_reviews_log` (если существует)
4. ✅ Переносит данные из старой таблицы (если необходимо)

## Изменения в API

### Новые возможности:
- Webhook `/api/v1/reviews/webhook` теперь проверяет дубликаты по `external_review_id`
- Методы репозитория `get_by_external_id()` и `exists_by_external_id()`
- Автоматическое предотвращение повторной обработки одинаковых отзывов

### Обновленные схемы:
```python
class ReviewBase(BaseModel):
    platform_id: UUID
    author_name: str
    rating: int = Field(..., ge=1, le=5)
    text: str
    external_review_id: Optional[str] = None  # Новое поле
    # ... остальные поля
```

## Интеграция с внешними системами

Теперь при получении отзыва через webhook можно передать `external_review_id`:

```json
{
    "platform_id": "uuid-platform",
    "author_name": "Иван Иванов", 
    "rating": 4,
    "text": "Отличный сервис!",
    "external_review_id": "google_maps_12345"
}
```

Система автоматически проверит, не обрабатывался ли уже этот отзыв ранее.