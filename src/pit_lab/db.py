"""Warehouse access helpers.

Thin, dependency-light wrappers around psycopg2 that give the rest of the
project three things:

* a connection context manager that always commits or always rolls back;
* a way to execute the ``.sql`` files under ``sql/`` as first-class artefacts
  rather than strings embedded in Python;
* ``explain_analyze``, used by the performance benchmarks.

Keeping the SQL in files matters for this project specifically: the hand-rolled
SCD Type 2 implementation is a *deliverable*, meant to be read by a reviewer.
Burying it in Python string literals would defeat that.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor, execute_values

from pit_lab.config import get_settings

logger = logging.getLogger(__name__)

# Matches a line that is entirely a SQL comment, used when deciding whether a
# chunk of a script carries an executable statement.
_COMMENT_LINE = re.compile(r"^\s*--")

# A /* ... */ block, stripped before the comment-only check above.
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

# A dollar-quote opener: $$ or $tag$ (PostgreSQL tags are identifier-shaped).
_DOLLAR_QUOTE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$")


@contextmanager
def connect(autocommit: bool = False) -> Iterator[PgConnection]:
    """Yield a warehouse connection, committing on success.

    Args:
        autocommit: When True, run outside a transaction. Required for
            statements PostgreSQL refuses to run transactionally, such as
            ``CREATE DATABASE`` and ``VACUUM``.

    Yields:
        An open psycopg2 connection, closed on exit.
    """
    settings = get_settings()
    conn = psycopg2.connect(settings.db.dsn)
    conn.autocommit = autocommit
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql: str, params: Sequence[Any] | None = None) -> None:
    """Execute a single statement that returns no rows."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)


def fetch_all(sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    """Execute a query and return every row as a dictionary."""
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(sql: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
    """Execute a query and return the first row, or None if there are none."""
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def _split_statements(script: str) -> list[str]:
    """Split a SQL script into individual statements on statement-terminating
    semicolons.

    A naive ``script.split(";")`` is wrong for this project's SQL: the
    ``COMMENT ON`` statements contain prose, and prose contains semicolons.
    Splitting on those produces unterminated string literals.

    This scanner tracks the four contexts in which a semicolon is *not* a
    terminator:

    * inside a single-quoted string (``''`` is an escaped quote, not a close);
    * inside a double-quoted identifier;
    * inside a ``--`` line comment;
    * inside a ``/* ... */`` block comment (PostgreSQL nests these).

    Dollar-quoted bodies (``$$ ... $$``, ``$tag$ ... $tag$``) are handled too,
    so adding a PL/pgSQL function later will not silently break the loader.
    """
    statements: list[str] = []
    current: list[str] = []

    in_single = in_double = in_line_comment = False
    block_depth = 0
    dollar_tag: str | None = None
    i = 0
    length = len(script)

    while i < length:
        char = script[i]
        pair = script[i : i + 2]

        # --- terminators for the context we are currently inside ----------
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            current.append(char)
            i += 1
            continue

        if block_depth:
            if pair == "*/":
                block_depth -= 1
                current.append(pair)
                i += 2
                continue
            if pair == "/*":
                block_depth += 1
                current.append(pair)
                i += 2
                continue
            current.append(char)
            i += 1
            continue

        if dollar_tag is not None:
            if script.startswith(dollar_tag, i):
                current.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            current.append(char)
            i += 1
            continue

        if in_single:
            # '' inside a string is a literal quote, not the closing delimiter.
            if pair == "''":
                current.append(pair)
                i += 2
                continue
            if char == "'":
                in_single = False
            current.append(char)
            i += 1
            continue

        if in_double:
            if char == '"':
                in_double = False
            current.append(char)
            i += 1
            continue

        # --- not inside anything: look for context openers ----------------
        if pair == "--":
            in_line_comment = True
            current.append(pair)
            i += 2
            continue

        if pair == "/*":
            block_depth = 1
            current.append(pair)
            i += 2
            continue

        if char == "'":
            in_single = True
            current.append(char)
            i += 1
            continue

        if char == '"':
            in_double = True
            current.append(char)
            i += 1
            continue

        if char == "$":
            match = _DOLLAR_QUOTE.match(script, i)
            if match:
                dollar_tag = match.group(0)
                current.append(dollar_tag)
                i += len(dollar_tag)
                continue

        # --- a real statement terminator ----------------------------------
        if char == ";":
            statements.append("".join(current))
            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    # Trailing text after the last semicolon (a script may omit the final one).
    statements.append("".join(current))

    return [s.strip() for s in statements if _carries_a_statement(s)]


def _carries_a_statement(chunk: str) -> bool:
    """True if a chunk contains anything other than whitespace and comments."""
    without_block_comments = _BLOCK_COMMENT.sub(" ", chunk)
    return any(
        line.strip() and not _COMMENT_LINE.match(line)
        for line in without_block_comments.splitlines()
    )


def run_script(path: Path, autocommit: bool = False) -> float:
    """Execute a ``.sql`` file and return its wall-clock duration in seconds.

    Args:
        path: Path to the SQL file, absolute or relative to the repo root.
        autocommit: Passed through to :func:`connect`.

    Returns:
        Elapsed seconds, so callers can report per-stage timings.
    """
    settings = get_settings()
    resolved = path if path.is_absolute() else settings.paths.root / path
    script = resolved.read_text(encoding="utf-8")
    statements = _split_statements(script)

    logger.info("Running %s (%d statements)", resolved.name, len(statements))
    started = time.perf_counter()
    with connect(autocommit=autocommit) as conn, conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    elapsed = time.perf_counter() - started
    logger.info("Finished %s in %.2fs", resolved.name, elapsed)
    return elapsed


def bulk_insert(table: str, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> int:
    """Insert many rows in a single round trip.

    Uses ``execute_values``, which batches the rows into one multi-VALUES
    statement. For the ~1.26M-row fact table this is roughly two orders of
    magnitude faster than ``executemany``.

    Returns:
        The number of rows inserted.
    """
    if not rows:
        return 0

    column_list = ", ".join(f'"{c}"' for c in columns)
    sql = f"INSERT INTO {table} ({column_list}) VALUES %s"

    with connect() as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=10_000)
    return len(rows)


def explain_analyze(sql: str, params: Sequence[Any] | None = None) -> str:
    """Return the ``EXPLAIN (ANALYZE, BUFFERS)`` plan for a query as text.

    Used by the performance benchmarks to capture real before/after plans
    rather than transcribing them by hand.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, TIMING ON) {sql}", params)
        return "\n".join(line[0] for line in cur.fetchall())


def table_exists(table: str, schema: str = "public") -> bool:
    """Check whether a table or view exists in the warehouse."""
    row = fetch_one(
        """
        SELECT 1 AS present
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return row is not None


def row_count(table: str) -> int:
    """Return the exact row count for a table."""
    row = fetch_one(f"SELECT COUNT(*) AS n FROM {table}")
    return int(row["n"]) if row else 0
