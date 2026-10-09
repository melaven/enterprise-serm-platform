-- 005_reviews_scraper_fields.sql
-- Поля RawReviewSchema, которых нет в базовой схеме reviews:
--   reply_text   ответ владельца бизнеса на отзыв
--   raw_metadata доп. данные площадки (лайки, тип визита и т.п.), JSON
-- Колонка называется raw_metadata, а не metadata: атрибут `metadata` зарезервирован
-- Declarative Base в SQLAlchemy. Под него в модели Review:
--   reply_text:   Mapped[str | None]
--   raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
BEGIN;

ALTER TABLE public.reviews
  ADD COLUMN IF NOT EXISTS reply_text   text,
  ADD COLUMN IF NOT EXISTS raw_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
