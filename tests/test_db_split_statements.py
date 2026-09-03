"""Tests for pit_lab.db._split_statements.

This function exists because of a real bug: the first version of the SQL
runner split scripts on every semicolon, which broke on the very first real
script it ran (a semicolon inside a COMMENT ON string literal). These tests
pin down the contexts that a naive split gets wrong.
"""

from __future__ import annotations

from pit_lab.db import _split_statements


def test_splits_simple_statements():
    script = "SELECT 1; SELECT 2;"
    assert _split_statements(script) == ["SELECT 1", "SELECT 2"]


def test_semicolon_inside_string_literal_is_not_a_split_point():
    script = "COMMENT ON TABLE t IS 'a sentence; with a semicolon.';"
    statements = _split_statements(script)
    assert len(statements) == 1
    assert "a sentence; with a semicolon." in statements[0]


def test_escaped_quote_inside_string_literal():
    script = "SELECT 'it''s; fine' AS x;"
    statements = _split_statements(script)
    assert len(statements) == 1
    assert statements[0] == "SELECT 'it''s; fine' AS x"


def test_semicolon_inside_double_quoted_identifier():
    script = 'SELECT 1 AS "weird;name";'
    statements = _split_statements(script)
    assert len(statements) == 1


def test_semicolon_inside_line_comment_is_ignored():
    script = "SELECT 1; -- a comment; with a semicolon\nSELECT 2;"
    statements = _split_statements(script)
    assert statements == ["SELECT 1", "-- a comment; with a semicolon\nSELECT 2"]


def test_semicolon_inside_block_comment_is_ignored():
    script = "SELECT 1; /* block; comment */ SELECT 2;"
    statements = _split_statements(script)
    assert len(statements) == 2
    assert "SELECT 2" in statements[1]


def test_dollar_quoted_body_with_semicolons():
    script = """
    DO $$
    BEGIN
        RAISE NOTICE 'one;two';
    END
    $$;
    """
    statements = _split_statements(script)
    assert len(statements) == 1
    assert "RAISE NOTICE" in statements[0]


def test_tagged_dollar_quote():
    script = "DO $scd$ SELECT 'a;b' $scd$;"
    statements = _split_statements(script)
    assert len(statements) == 1


def test_comment_only_chunk_is_dropped():
    script = "SELECT 1;\n-- trailing comment, no statement\n"
    statements = _split_statements(script)
    assert statements == ["SELECT 1"]


def test_trailing_statement_without_final_semicolon():
    script = "SELECT 1; SELECT 2"
    statements = _split_statements(script)
    assert statements == ["SELECT 1", "SELECT 2"]


def test_empty_script_returns_no_statements():
    assert _split_statements("") == []
    assert _split_statements("   \n  -- only a comment\n") == []


def test_realistic_comment_on_column_with_semicolon_in_prose():
    # This is the exact shape that broke the naive split() in production:
    # sql/bronze/02_create_bronze_tables.sql's COMMENT ON COLUMN statements.
    script = (
        "COMMENT ON COLUMN bronze.sp500_current_snapshot.cik IS\n"
        "    'SEC Central Index Key. Stored as TEXT to preserve leading zeros; '\n"
        "    'it is the only stable identifier here.';"
    )
    statements = _split_statements(script)
    assert len(statements) == 1
