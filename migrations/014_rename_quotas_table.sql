-- Migration: 014_rename_quotas_table.sql
-- Description: Переименование organization_quotas -> tenant_quotas для согласованности с новой схемой
-- Depends: 008_billing_quotas.sql

BEGIN;

-- 1. Переименовать таблицу
ALTER TABLE IF EXISTS organization_quotas RENAME TO tenant_quotas;

-- 2. Переименовать колонку org_id -> tenant_id
ALTER TABLE IF EXISTS tenant_quotas RENAME COLUMN org_id TO tenant_id;

-- 3. Переименовать constraint
ALTER TABLE tenant_quotas RENAME CONSTRAINT unique_org_quota TO unique_tenant_quota;

-- 4. Переименовать индексы
ALTER INDEX IF EXISTS idx_org_quotas_org_id RENAME TO idx_tenant_quotas_tenant_id;
ALTER INDEX IF EXISTS idx_org_quotas_active RENAME TO idx_tenant_quotas_active;

-- 5. Обновить поля для соответствия новой схеме (app/services/billing.py)
-- Добавляем недостающие колонки для tenant_quotas

-- Переименовать requests_used -> reviews_parsed_used (для соответствия схеме)
ALTER TABLE tenant_quotas RENAME COLUMN requests_used TO reviews_parsed_used;

-- Добавить новые колонки для LLM токенов
ALTER TABLE tenant_quotas 
    ADD COLUMN IF NOT EXISTS reviews_parsed_limit BIGINT DEFAULT 500,
    ADD COLUMN IF NOT EXISTS llm_tokens_used BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS llm_tokens_limit BIGINT DEFAULT 100000,
    ADD COLUMN IF NOT EXISTS reset_date TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '30 days');

-- Синхронизировать reviews_parsed_limit с billing_plans.max_requests
UPDATE tenant_quotas tq
SET reviews_parsed_limit = bp.max_requests
FROM billing_plans bp
WHERE tq.plan_id = bp.id;

-- Создать индекс для reset_date (для периодических задач сброса)
CREATE INDEX IF NOT EXISTS idx_tenant_quotas_reset_date ON tenant_quotas(reset_date);

COMMIT;
