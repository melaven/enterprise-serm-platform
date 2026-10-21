DO $$
DECLARE
    table_row record;
BEGIN
    FOR table_row IN
        SELECT
            tables.tablename,
            relations.relrowsecurity,
            EXISTS (
                SELECT 1
                FROM pg_attribute
                WHERE attrelid = relations.oid
                  AND attname = 'tenant_id'
                  AND attnum > 0
                  AND NOT attisdropped
            ) AS has_tenant_id
        FROM pg_tables AS tables
        JOIN pg_namespace AS namespaces
          ON namespaces.nspname = tables.schemaname
        JOIN pg_class AS relations
          ON relations.relnamespace = namespaces.oid
         AND relations.relname = tables.tablename
        WHERE tables.schemaname = 'public'
    LOOP
        IF NOT table_row.relrowsecurity THEN
            EXECUTE format(
                'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
                'public',
                table_row.tablename
            );
        END IF;

        EXECUTE format(
            'DROP POLICY IF EXISTS public_deny_anon ON %I.%I',
            'public',
            table_row.tablename
        );
        EXECUTE format(
            'CREATE POLICY public_deny_anon ON %I.%I AS RESTRICTIVE '
            'FOR ALL TO anon USING (false) WITH CHECK (false)',
            'public',
            table_row.tablename
        );

        IF table_row.has_tenant_id THEN
            EXECUTE format(
                'DROP POLICY IF EXISTS public_tenant_access ON %I.%I',
                'public',
                table_row.tablename
            );
            EXECUTE format(
                'DROP POLICY IF EXISTS public_tenant_boundary ON %I.%I',
                'public',
                table_row.tablename
            );
            EXECUTE format(
                $policy$
                CREATE POLICY public_tenant_access ON %I.%I
                FOR ALL TO authenticated
                USING (
                    tenant_id::text =
                    (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> %L)
                )
                WITH CHECK (
                    tenant_id::text =
                    (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> %L)
                )
                $policy$,
                'public',
                table_row.tablename,
                'tenant_id',
                'tenant_id'
            );
            EXECUTE format(
                $policy$
                CREATE POLICY public_tenant_boundary ON %I.%I
                AS RESTRICTIVE FOR ALL TO authenticated
                USING (
                    tenant_id::text =
                    (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> %L)
                )
                WITH CHECK (
                    tenant_id::text =
                    (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> %L)
                )
                $policy$,
                'public',
                table_row.tablename,
                'tenant_id',
                'tenant_id'
            );
        END IF;
    END LOOP;
END
$$;
