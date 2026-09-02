"""Centralised configuration for the Point-in-Time Analytics Lab.

Every path and credential used by the pipeline resolves through this module, so
that ingestion, transformation, export and the dashboard all agree on where
things live. Values come from the environment (optionally via a ``.env`` file),
with defaults that match both the native PostgreSQL install and
``docker-compose.yml``.

The repository root is derived from this file's location rather than from the
current working directory, so scripts behave identically whether they are run
from the root, from ``dbt_pit/``, or from an IDE's run button.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

# --------------------------------------------------------------------------
# Repository layout
# --------------------------------------------------------------------------
# config.py lives at <root>/src/pit_lab/config.py, hence three levels up.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Load ``.env`` into the process environment if python-dotenv is present.

    The dependency is optional on purpose: the dashboard's deployment surface
    (``requirements.txt``) does not include python-dotenv, because Streamlit
    Community Cloud injects configuration through its own secrets mechanism.
    Falling back silently keeps a single code path for both environments.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(REPO_ROOT / ".env", override=False)


_load_dotenv()


def _env_path(key: str, default: str) -> Path:
    """Resolve an environment-provided path against the repository root."""
    raw = os.getenv(key, default)
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _env_date(key: str, default: str) -> date:
    return date.fromisoformat(os.getenv(key, default))


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """PostgreSQL connection parameters for the warehouse."""

    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str

    @property
    def dsn(self) -> str:
        """libpq connection string, used by psycopg2."""
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}"
        )

    @property
    def sqlalchemy_url(self) -> str:
        """SQLAlchemy URL, used by pandas ``to_sql`` / ``read_sql``."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    def __repr__(self) -> str:  # pragma: no cover - defensive nicety
        """Redact the password so the config never leaks into a traceback."""
        return (
            f"DatabaseConfig(host={self.host!r}, port={self.port}, "
            f"database={self.database!r}, user={self.user!r}, "
            f"password='***', schema={self.schema!r})"
        )


@dataclass(frozen=True, slots=True)
class Paths:
    """Filesystem locations for every pipeline stage."""

    root: Path
    raw_prices: Path
    raw_reference: Path
    interim: Path
    processed: Path
    sql: Path
    dbt_project: Path
    assets: Path

    def ensure(self) -> None:
        """Create the directories the pipeline writes to.

        Read-only locations (``sql``, ``dbt_project``, ``assets``) are excluded:
        if those are missing, something is wrong with the checkout and silently
        creating an empty directory would mask the real error.
        """
        for directory in (self.raw_prices, self.raw_reference, self.interim, self.processed):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class AnalysisWindow:
    """Date bounds for the return calculations.

    The raw corpus starts on 2015-12-21, but cumulative returns are only
    comparable across sectors when every series starts on the same date, so the
    analysis window is clipped to the first full calendar year.
    """

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError(f"Analysis window start ({self.start}) must precede end ({self.end})")


@dataclass(frozen=True, slots=True)
class Settings:
    """Top-level configuration object."""

    db: DatabaseConfig
    paths: Paths
    window: AnalysisWindow


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build (and memoise) the settings object from the environment."""
    db = DatabaseConfig(
        host=os.getenv("PIT_DB_HOST", "localhost"),
        port=int(os.getenv("PIT_DB_PORT", "5432")),
        database=os.getenv("PIT_DB_NAME", "pit_lab"),
        user=os.getenv("PIT_DB_USER", "postgres"),
        password=os.getenv("PIT_DB_PASSWORD", "pitlab_dev_2026"),
        schema=os.getenv("PIT_DB_SCHEMA", "public"),
    )

    paths = Paths(
        root=REPO_ROOT,
        raw_prices=_env_path("PIT_RAW_PRICES_DIR", "data/raw/prices"),
        raw_reference=_env_path("PIT_RAW_REFERENCE_DIR", "data/raw/reference"),
        interim=_env_path("PIT_INTERIM_DIR", "data/interim"),
        processed=_env_path("PIT_PROCESSED_DIR", "data/processed"),
        sql=REPO_ROOT / "sql",
        dbt_project=REPO_ROOT / "dbt_pit",
        assets=REPO_ROOT / "assets",
    )

    window = AnalysisWindow(
        start=_env_date("PIT_ANALYSIS_START", "2016-01-01"),
        end=_env_date("PIT_ANALYSIS_END", "2025-12-19"),
    )

    return Settings(db=db, paths=paths, window=window)
