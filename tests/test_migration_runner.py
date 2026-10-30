from scripts.migrate import (
    MIGRATIONS,
    MIGRATIONS_DIR,
    migration_statements,
    split_sql_statements,
)


def test_sql_splitter_preserves_quoted_and_dollar_quoted_semicolons() -> None:
    sql = """
    INSERT INTO demo(value) VALUES ('first; second');
    DO $body$
    BEGIN
        PERFORM 'inside; body';
    END;
    $body$;
    /* outer ; /* nested ; */ still outer */
    SELECT "semi;colon" FROM demo;
    """

    statements = split_sql_statements(sql)

    assert len(statements) == 3
    assert "'first; second'" in statements[0]
    assert "PERFORM 'inside; body';" in statements[1]
    assert "nested ;" in statements[2]
    assert '"semi;colon"' in statements[2]


def test_migration_statements_drop_only_script_transaction_wrappers() -> None:
    sql = """
    -- runner owns transactions
    BEGIN;
    CREATE TABLE demo(value text);
    COMMIT;
    """

    statements = migration_statements(sql)

    assert len(statements) == 1
    assert statements[0].endswith("CREATE TABLE demo(value text)")


def test_migration_chain_respects_dependencies_and_all_files_exist() -> None:
    assert (
        MIGRATIONS.index("009_billing_seed.sql")
        < MIGRATIONS.index("014_rename_quotas_table.sql")
        < MIGRATIONS.index("013_stripe_billing.sql")
    )
    assert all((MIGRATIONS_DIR / filename).is_file() for filename in MIGRATIONS)
    assert all(
        migration_statements((MIGRATIONS_DIR / filename).read_text(encoding="utf-8"))
        for filename in MIGRATIONS
    )


def test_quota_service_migration_matches_runtime_contract() -> None:
    sql = (MIGRATIONS_DIR / "015_quota_service_contract.sql").read_text(
        encoding="utf-8"
    )
    statements = migration_statements(sql)

    assert any("ADD COLUMN IF NOT EXISTS reserved_llm_tokens" in s for s in statements)
    assert any("ADD COLUMN IF NOT EXISTS created_at" in s for s in statements)
    for function_name in (
        "check_quota_available",
        "reserve_llm_tokens",
        "commit_llm_tokens",
        "release_llm_tokens",
        "consume_reviews",
    ):
        assert any(f"FUNCTION public.{function_name}" in s for s in statements)


def test_stripe_billing_uses_existing_tenant_context_function() -> None:
    sql = (MIGRATIONS_DIR / "013_stripe_billing.sql").read_text(encoding="utf-8")

    assert "app.current_company_id()" in sql
    assert "app.current_tenant_id()" not in sql


def test_entitlement_fix_migration_defines_quota_rollover() -> None:
    filename = "036_fix_entitlement_tenant_context.sql"
    assert filename in MIGRATIONS

    sql = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION app.roll_quota_period" in sql
    assert "CREATE OR REPLACE FUNCTION app.get_entitlement" in sql
    assert "app.current_company_id()" in sql


def test_sanitized_reviews_migration_adds_scoped_deduplication_and_pii_checks() -> None:
    filename = "037_sanitized_reviews.sql"
    assert filename in MIGRATIONS

    sql = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS external_id varchar(255)" in sql
    assert "ADD COLUMN IF NOT EXISTS author_hash varchar(32)" in sql
    assert "uq_reviews_company_platform_external_id" in sql
    assert "author_display IN ('Клиент', 'Анонимный клиент')" in sql
    assert "reviews_external_id_hash_chk" in sql
    assert "reviews_author_hash_chk" in sql


def test_review_ingestion_migration_aligns_deduplication_schema() -> None:
    filename = "038_review_ingest_dedup_indexes.sql"
    assert filename in MIGRATIONS

    sql = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    assert "ALTER COLUMN platform_id DROP NOT NULL" in sql
    assert "DROP INDEX IF EXISTS public.uq_reviews_analytics_dedup" in sql
    assert "DROP INDEX IF EXISTS public.uq_reviews_company_platform_external_id" in sql
    assert (
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_tenant_platform_external_id"
        in sql
    )
    assert "ON public.reviews (company_id, platform, external_id)" in sql
    assert "WHERE" not in sql


def test_schema_cleanup_migration_removes_duplicate_review_pipeline_state() -> None:
    sql = (MIGRATIONS_DIR / "028_schema_cleanup.sql").read_text(encoding="utf-8")

    assert "DROP COLUMN IF EXISTS ai_attempts" in sql
    assert "DROP COLUMN IF EXISTS is_dlq" in sql
    assert "SET retry_count = GREATEST(retry_count, COALESCE(ai_attempts, 0))" in sql
    assert "WHERE dlq_reason IS NOT NULL" in sql


def test_pii_migration_anonymizes_names_and_clears_optional_profile_urls() -> None:
    sql = (MIGRATIONS_DIR / "029_anonymize_pii.sql").read_text(encoding="utf-8")

    assert "SET author_name = 'Анонимный клиент ' || substr(md5(id::text), 1, 6)" in sql
    assert "WHERE author_name NOT LIKE 'Анонимный клиент%'" in sql
    assert "author_avatar_url = NULL" in sql
    assert "author_profile_url = NULL" in sql


def test_review_data_minimization_migration_is_registered_and_cleans_stored_data() -> (
    None
):
    assert "030_review_data_minimization.sql" in MIGRATIONS
    sql = (MIGRATIONS_DIR / "030_review_data_minimization.sql").read_text(
        encoding="utf-8"
    )
    assert "author_name = 'Автор отзыва'" in sql
    assert "external_review_id = NULL" in sql
    assert "si_response = NULL" in sql
    assert "raw_metadata = '{}'::jsonb" in sql
    assert "DELETE FROM public.llm_cache" in sql
    assert "uq_reviews_analytics_dedup" in sql


def test_rls_enforcement_migration_covers_public_tables_and_tenants() -> None:
    filename = "031_enforce_rls_all_tables.sql"
    assert filename in MIGRATIONS

    sql = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    statements = migration_statements(sql)

    assert len(statements) == 1
    assert "FROM pg_tables" in sql
    assert "WHERE tables.schemaname = 'public'" in sql
    assert "ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY" in sql
    assert "AS RESTRICTIVE" in sql
    assert "FOR ALL TO anon" in sql
    assert "USING (false) WITH CHECK (false)" in sql
    assert "FOR ALL TO authenticated" in sql
    assert "current_setting('request.jwt.claims', true)" in sql


def test_review_analysis_payload_migration_is_registered_and_tenant_isolated() -> None:
    filename = "034_review_analysis_payload.sql"
    assert filename in MIGRATIONS

    sql = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS public.review_analysis_payloads" in sql
    assert "encrypted_text text NOT NULL" in sql
    assert "ALTER TABLE public.review_analysis_payloads FORCE ROW LEVEL SECURITY" in sql
    assert "company_id = app.current_company_id()" in sql


def test_review_replies_migration_is_registered_and_tenant_isolated() -> None:
    filename = "035_review_replies.sql"
    assert filename in MIGRATIONS

    sql = (MIGRATIONS_DIR / filename).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS public.review_replies" in sql
    assert "reply_text text NOT NULL" in sql
    assert "ALTER TABLE public.review_replies FORCE ROW LEVEL SECURITY" in sql
    assert "company_id = app.current_company_id()" in sql


def test_admin_quota_migration_restricts_direct_limit_updates() -> None:
    sql = (MIGRATIONS_DIR / "016_admin_quota_updates.sql").read_text(encoding="utf-8")
    statements = migration_statements(sql)

    assert any(
        "REVOKE UPDATE ON public.tenant_quotas FROM app_tenant" in s for s in statements
    )
    assert any("FUNCTION public.update_quota_limits" in s for s in statements)
    assert any("member.role IN ('owner', 'admin')" in s for s in statements)
    assert any(
        "p_actor_id IS DISTINCT FROM app.current_user_id()" in s for s in statements
    )


def test_repository_sql_files_are_kept_in_migrations() -> None:
    root = MIGRATIONS_DIR.parent
    source_dirs = (root / "app", root / "scripts", root / "tests")
    assert not list(root.glob("*.sql"))
    assert all(
        not list(source_dir.rglob("*.sql"))
        for source_dir in source_dirs
        if source_dir.exists()
    )
    assert all((MIGRATIONS_DIR / filename).is_file() for filename in MIGRATIONS)
