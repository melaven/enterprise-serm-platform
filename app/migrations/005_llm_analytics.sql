-- 005_llm_analytics.sql
-- Добавление полей для хранения LLM-аналитики отзывов
-- Применять под миграционной ролью (postgres), НЕ под app_tenant.
-- Идемпотентные операции: можно применять многократно.

BEGIN;

-- 1. Добавляем поле raw_metadata для хранения JSON с LLM-аналитикой
ALTER TABLE public.reviews 
  ADD COLUMN IF NOT EXISTS raw_metadata jsonb;

-- 2. Добавляем поле reply_text для хранения сгенерированных ответов
-- (si_response уже существует, но может быть переименовано для ясности)
ALTER TABLE public.reviews 
  ADD COLUMN IF NOT EXISTS reply_text text;

-- 3. Создаем индекс для быстрого поиска по LLM-тегам в JSON
CREATE INDEX IF NOT EXISTS ix_reviews_llm_tags 
  ON public.reviews USING gin ((raw_metadata -> 'tags'));

-- 4. Создаем индекс для поиска по тональности
CREATE INDEX IF NOT EXISTS ix_reviews_sentiment 
  ON public.reviews ((raw_metadata ->> 'sentiment'));

-- 5. Добавляем комментарии для документации
COMMENT ON COLUMN public.reviews.raw_metadata IS 
  'LLM-аналитика отзыва: тональность, теги, метаданные (JSON)';

COMMENT ON COLUMN public.reviews.reply_text IS 
  'Сгенерированный LLM ответ на отзыв';

-- 6. Создаем вспомогательную функцию для извлечения тегов
CREATE OR REPLACE FUNCTION get_review_tags(metadata jsonb)
RETURNS text[] AS $$
BEGIN
  IF metadata IS NULL THEN
    RETURN ARRAY[]::text[];
  END IF;
  
  RETURN ARRAY(
    SELECT jsonb_array_elements_text(metadata -> 'tags')
    WHERE metadata -> 'tags' IS NOT NULL
  );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION get_review_tags(jsonb) IS 
  'Извлекает массив тегов из LLM-метаданных отзыва';

-- Migration 005_llm_analytics.sql completed successfully

COMMIT;