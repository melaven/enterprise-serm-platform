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


def test_migration_chain_is_ordered_and_all_files_exist() -> None:
    assert MIGRATIONS == tuple(sorted(MIGRATIONS))
    assert all((MIGRATIONS_DIR / filename).is_file() for filename in MIGRATIONS)
    assert all(
        migration_statements((MIGRATIONS_DIR / filename).read_text(encoding="utf-8"))
        for filename in MIGRATIONS
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
