-- 004_reviews_dedup.sql
-- Добавление новых полей для поддержки парсинга и дедупликации отзывов
-- Применять под миграционной ролью (postgres), НЕ под app_tenant.
-- Идемпотентные операции: можно применять многократно.

BEGIN;

-- 1. Добавляем поля для парсинга отзывов
ALTER TABLE public.reviews 
  ADD COLUMN IF NOT EXISTS platform text,
  ADD COLUMN IF NOT EXISTS external_review_id text;

-- 2. Добавляем поле platform_url в таблицу platforms
ALTER TABLE public.platforms
  ADD COLUMN IF NOT EXISTS platform_url text;

-- 3. Создаем индексы для производительности
CREATE INDEX IF NOT EXISTS ix_reviews_platform_name 
  ON public.reviews (platform);

CREATE INDEX IF NOT EXISTS ix_reviews_external_id 
  ON public.reviews (external_review_id);

CREATE INDEX IF NOT EXISTS ix_platforms_url 
  ON public.platforms (platform_url);

-- 4. Уникальный индекс для предотвращения дубликатов отзывов
-- Дубликаты определяются по внешнему ID в рамках platform
-- (так как reviews связан с platform, а platform с company_id)
CREATE UNIQUE INDEX IF NOT EXISTS reviews_external_id_platform_uq
  ON public.reviews (platform_id, external_review_id)
  WHERE external_review_id IS NOT NULL;

-- 5. Обновляем права доступа для app_tenant к новым полям
-- (права на таблицы уже даны в предыдущих миграциях)

-- 6. Добавляем комментарии для документации
COMMENT ON COLUMN public.reviews.platform IS 
  'Название платформы как строка для упрощения парсинга и аналитики';

COMMENT ON COLUMN public.reviews.external_review_id IS 
  'Внешний ID отзыва из источника (Google Maps, 2GIS, Trustpilot и др.)';

COMMENT ON COLUMN public.platforms.platform_url IS 
  'URL платформы для парсинга отзывов';

-- 7. Проверяем что RLS политики применятся к новым полям автоматически
-- (так как они уже настроены на уровне таблицы в 001_multitenancy_rls.sql)

-- Migration 004_reviews_dedup.sql completed successfully

COMMIT;