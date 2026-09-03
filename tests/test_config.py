"""Tests for pit_lab.config."""

from __future__ import annotations

from datetime import date

import pytest

from pit_lab.config import AnalysisWindow, get_settings


def test_get_settings_is_memoised():
    """get_settings() must return the same object on repeated calls, since
    every module in the pipeline relies on sharing one settings instance."""
    assert get_settings() is get_settings()


def test_paths_resolve_under_repo_root():
    settings = get_settings()
    assert settings.paths.raw_prices.is_relative_to(settings.paths.root)
    assert settings.paths.processed.is_relative_to(settings.paths.root)


def test_analysis_window_rejects_inverted_range():
    with pytest.raises(ValueError, match="must precede"):
        AnalysisWindow(start=date(2020, 1, 1), end=date(2019, 1, 1))


def test_analysis_window_accepts_valid_range():
    window = AnalysisWindow(start=date(2016, 1, 1), end=date(2025, 12, 19))
    assert window.start < window.end


def test_database_config_repr_redacts_password():
    settings = get_settings()
    assert settings.db.password not in repr(settings.db)
    assert "***" in repr(settings.db)


def test_database_config_dsn_contains_credentials():
    settings = get_settings()
    dsn = settings.db.dsn
    assert settings.db.password in dsn
    assert settings.db.database in dsn
