-- Migration: 009_billing_seed.sql
-- Description: Seed data for billing system (plans + test quota)

-- 1. Seed billing plans (3 tiers)
INSERT INTO billing_plans (name, max_requests, price_usd) 
VALUES 
    ('Starter', 1000, 29.00),
    ('Pro', 10000, 99.00),
    ('Enterprise', 100000, 499.00)
ON CONFLICT (name) DO NOTHING;

-- 2. Create test organization quota
-- Using valid UUID: 11111111-1111-1111-1111-111111111111
INSERT INTO organization_quotas (
    org_id, 
    plan_id, 
    requests_used, 
    billing_cycle_end,
    is_active
) 
SELECT 
    '11111111-1111-1111-1111-111111111111'::uuid,
    id,
    0,
    NOW() + INTERVAL '30 days',
    true
FROM billing_plans 
WHERE name = 'Starter'
ON CONFLICT (org_id) DO NOTHING;

-- Verify seed data
SELECT 
    'Billing Plans Seeded' as step,
    COUNT(*) as count 
FROM billing_plans;

SELECT 
    'Test Quota Created' as step,
    COUNT(*) as count 
FROM organization_quotas 
WHERE org_id = '11111111-1111-1111-1111-111111111111'::uuid;
