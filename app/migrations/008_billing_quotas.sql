-- Migration: 008_billing_quotas.sql
-- Description: Изолированная система квот и биллинга (Zero Trust)

-- 1. Справочник тарифов
CREATE TABLE IF NOT EXISTS billing_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE, -- например: 'Starter', 'Pro', 'Enterprise'
    max_requests INT NOT NULL,        -- лимит запросов к AI/Парсерам
    price_usd DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Квоты конкретных клиентов (организаций)
CREATE TABLE IF NOT EXISTS organization_quotas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL, -- Внешний ключ на твою таблицу организаций/клиентов
    plan_id UUID NOT NULL REFERENCES billing_plans(id),
    requests_used INT DEFAULT 0,
    billing_cycle_end TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_org_quota UNIQUE (org_id)
);

-- 3. Индексы для моментальной проверки квот при каждом API-запросе (критично для скорости)
CREATE INDEX idx_org_quotas_org_id ON organization_quotas(org_id);
CREATE INDEX idx_org_quotas_active ON organization_quotas(is_active);
