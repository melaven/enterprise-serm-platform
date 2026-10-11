-- ============================================================================
-- Миграция 008: Биллинг и квоты для мультитенантности
-- ============================================================================
-- Создаёт таблицу tenant_quotas для учёта использования LLM-токенов и отзывов
-- с атомарными операциями резервирования/списания через транзакции.
--
-- Применение: psql -h HOST -U USER -d DB -f 008_billing_quotas.sql
-- ============================================================================

BEGIN;

-- Таблица квот: одна строка на tenant_id
CREATE TABLE IF NOT EXISTS tenant_quotas (
    tenant_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Лимиты (устанавливаются администратором)
    max_llm_tokens INTEGER NOT NULL DEFAULT 100000,
    max_reviews INTEGER NOT NULL DEFAULT 500,
    
    -- Текущее использование
    used_llm_tokens INTEGER NOT NULL DEFAULT 0,
    used_reviews INTEGER NOT NULL DEFAULT 0,
    
    -- Зарезервированные ресурсы (для оценочного списания до точного подсчёта)
    reserved_llm_tokens INTEGER NOT NULL DEFAULT 0,
    
    -- Метаданные
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ограничения: использование не может быть отрицательным
    CONSTRAINT positive_used_tokens CHECK (used_llm_tokens >= 0),
    CONSTRAINT positive_used_reviews CHECK (used_reviews >= 0),
    CONSTRAINT positive_reserved_tokens CHECK (reserved_llm_tokens >= 0),
    CONSTRAINT positive_max_tokens CHECK (max_llm_tokens > 0),
    CONSTRAINT positive_max_reviews CHECK (max_reviews > 0)
);

-- Индексы для быстрого поиска превышений квот
CREATE INDEX IF NOT EXISTS idx_tenant_quotas_token_usage 
    ON tenant_quotas(tenant_id, used_llm_tokens, max_llm_tokens);
    
CREATE INDEX IF NOT EXISTS idx_tenant_quotas_review_usage 
    ON tenant_quotas(tenant_id, used_reviews, max_reviews);

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_tenant_quotas_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tenant_quotas_updated_at ON tenant_quotas;
CREATE TRIGGER tenant_quotas_updated_at
    BEFORE UPDATE ON tenant_quotas
    FOR EACH ROW
    EXECUTE FUNCTION update_tenant_quotas_timestamp();

-- ============================================================================
-- Функция автоматической инициализации квот для новых компаний
-- ============================================================================
-- При создании нового пользователя (компании) автоматически создаёт запись
-- с дефолтными лимитами: 100k токенов, 500 отзывов
CREATE OR REPLACE FUNCTION initialize_tenant_quota()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO tenant_quotas (
        tenant_id,
        max_llm_tokens,
        max_reviews,
        used_llm_tokens,
        used_reviews,
        reserved_llm_tokens
    ) VALUES (
        NEW.id,
        100000,  -- 100k токенов по умолчанию
        500,     -- 500 отзывов по умолчанию
        0,
        0,
        0
    )
    ON CONFLICT (tenant_id) DO NOTHING;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created_init_quota ON auth.users;
CREATE TRIGGER on_auth_user_created_init_quota
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION initialize_tenant_quota();

-- ============================================================================
-- Раздача квот существующим компаниям (идемпотентно)
-- ============================================================================
INSERT INTO tenant_quotas (tenant_id, max_llm_tokens, max_reviews)
SELECT 
    id,
    100000,  -- 100k токенов
    500      -- 500 отзывов
FROM auth.users
ON CONFLICT (tenant_id) DO NOTHING;

-- ============================================================================
-- RLS политики: каждый tenant видит только свои квоты
-- ============================================================================
ALTER TABLE tenant_quotas ENABLE ROW LEVEL SECURITY;

-- Политика чтения: пользователь видит только свои квоты
DROP POLICY IF EXISTS tenant_quotas_select_own ON tenant_quotas;
CREATE POLICY tenant_quotas_select_own ON tenant_quotas
    FOR SELECT
    USING (tenant_id = auth.uid());

-- Политика обновления: пользователь может обновлять только свои квоты
-- (в реальности обновление делает backend с service_role, но политику оставляем для симметрии)
DROP POLICY IF EXISTS tenant_quotas_update_own ON tenant_quotas;
CREATE POLICY tenant_quotas_update_own ON tenant_quotas
    FOR UPDATE
    USING (tenant_id = auth.uid());

-- ============================================================================
-- Вспомогательные функции для атомарного управления квотами
-- ============================================================================

-- Проверка доступности квоты (без списания)
CREATE OR REPLACE FUNCTION check_quota_available(
    p_tenant_id UUID,
    p_tokens_needed INTEGER DEFAULT 0,
    p_reviews_needed INTEGER DEFAULT 0
)
RETURNS BOOLEAN AS $$
DECLARE
    v_quota RECORD;
BEGIN
    SELECT 
        max_llm_tokens,
        max_reviews,
        used_llm_tokens + reserved_llm_tokens AS total_tokens_committed,
        used_reviews
    INTO v_quota
    FROM tenant_quotas
    WHERE tenant_id = p_tenant_id
    FOR UPDATE;  -- Блокируем строку для атомарности
    
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    
    -- Проверяем, что после списания не превысим лимиты
    IF p_tokens_needed > 0 THEN
        IF v_quota.total_tokens_committed + p_tokens_needed > v_quota.max_llm_tokens THEN
            RETURN FALSE;
        END IF;
    END IF;
    
    IF p_reviews_needed > 0 THEN
        IF v_quota.used_reviews + p_reviews_needed > v_quota.max_reviews THEN
            RETURN FALSE;
        END IF;
    END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Резервирование токенов (оценочное списание)
CREATE OR REPLACE FUNCTION reserve_llm_tokens(
    p_tenant_id UUID,
    p_tokens INTEGER
)
RETURNS BOOLEAN AS $$
DECLARE
    v_available BOOLEAN;
BEGIN
    -- Проверяем доступность и резервируем атомарно
    SELECT check_quota_available(p_tenant_id, p_tokens, 0) INTO v_available;
    
    IF NOT v_available THEN
        RETURN FALSE;
    END IF;
    
    UPDATE tenant_quotas
    SET reserved_llm_tokens = reserved_llm_tokens + p_tokens
    WHERE tenant_id = p_tenant_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Списание токенов и возврат разницы (точное списание после получения usage_metadata)
CREATE OR REPLACE FUNCTION commit_llm_tokens(
    p_tenant_id UUID,
    p_reserved_tokens INTEGER,
    p_actual_tokens INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE tenant_quotas
    SET 
        used_llm_tokens = used_llm_tokens + p_actual_tokens,
        reserved_llm_tokens = reserved_llm_tokens - p_reserved_tokens
    WHERE tenant_id = p_tenant_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Tenant % not found for token commit', p_tenant_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Возврат зарезервированных токенов (в случае ошибки)
CREATE OR REPLACE FUNCTION release_llm_tokens(
    p_tenant_id UUID,
    p_tokens INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE tenant_quotas
    SET reserved_llm_tokens = GREATEST(0, reserved_llm_tokens - p_tokens)
    WHERE tenant_id = p_tenant_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Tenant % not found for token release', p_tenant_id;
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Списание отзывов (вызывается после успешного сохранения)
CREATE OR REPLACE FUNCTION consume_reviews(
    p_tenant_id UUID,
    p_count INTEGER
)
RETURNS BOOLEAN AS $$
DECLARE
    v_available BOOLEAN;
BEGIN
    SELECT check_quota_available(p_tenant_id, 0, p_count) INTO v_available;
    
    IF NOT v_available THEN
        RETURN FALSE;
    END IF;
    
    UPDATE tenant_quotas
    SET used_reviews = used_reviews + p_count
    WHERE tenant_id = p_tenant_id;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMIT;

-- ============================================================================
-- Проверка применения миграции
-- ============================================================================
-- Должны быть записи для всех существующих пользователей
-- SELECT COUNT(*) FROM tenant_quotas;
-- SELECT tenant_id, max_llm_tokens, max_reviews, used_llm_tokens, used_reviews 
-- FROM tenant_quotas 
-- LIMIT 5;
