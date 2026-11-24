"""Unit tests for AnalyticsSettings, logging configuration, and Pydantic v2 schemas."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import ValidationError
import pytest

from unicorn_analytics.config import AnalyticsSettings, configure_logging
from unicorn_analytics.schemas import CohortAnalysisRequest, UnicornRecord


def test_analytics_settings_defaults_valid() -> None:
    """Default AnalyticsSettings should pass validation with safe operational bounds."""
    # Arrange & Act
    settings = AnalyticsSettings().validate()

    # Assert
    assert settings.db_path == ":memory:"
    assert settings.timeout_seconds == 10.0
    assert settings.default_num_companies == 100
    assert settings.random_seed == 42
    assert settings.rate_limit_per_minute >= 1


def test_analytics_settings_from_env_parses_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """from_env should parse typed values from .env while respecting OS precedence."""
    # Arrange
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DB_PATH=data/test.db\n"
        "DB_TIMEOUT_SECONDS=15.5\n"
        "DEFAULT_NUM_COMPANIES=250\n"
        "RANDOM_SEED=99\n"
        "ALLOWED_ORIGINS=https://app.example.com, http://localhost:5173/\n"
        "LOG_LEVEL=debug\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("DB_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("DEFAULT_NUM_COMPANIES", raising=False)
    monkeypatch.delenv("RANDOM_SEED", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    # Act
    settings = AnalyticsSettings.from_env(env_file=env_file)

    # Assert
    assert settings.db_path == "data/test.db"
    assert settings.timeout_seconds == 15.5
    assert settings.default_num_companies == 250
    assert settings.random_seed == 99
    assert settings.allowed_origins == ("https://app.example.com", "http://localhost:5173")
    assert settings.log_level == "DEBUG"


def test_analytics_settings_rejects_wildcard_origin() -> None:
    """Wildcard CORS origins must be rejected to maintain explicit allowlist security."""
    # Arrange
    settings = AnalyticsSettings(allowed_origins=("*",))

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid ALLOWED_ORIGINS"):
        settings.validate()


def test_analytics_settings_rejects_invalid_numeric_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed numeric env vars must raise explicit ValueError rather than failing later."""
    # Arrange
    monkeypatch.setenv("DEFAULT_NUM_COMPANIES", "not-an-int")

    # Act & Assert
    with pytest.raises(ValueError, match="DEFAULT_NUM_COMPANIES"):
        AnalyticsSettings.from_env()


def test_configure_logging_rejects_invalid_level() -> None:
    """configure_logging should reject unknown log levels upfront."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="Unsupported LOG_LEVEL"):
        configure_logging("VERBOSE_UNKNOWN")


def test_unicorn_record_rejects_founding_after_joined() -> None:
    """UnicornRecord must reject records where year_founded exceeds date_joined year."""
    # Arrange
    payload = {
        "company_id": 1,
        "company": "FutureTech",
        "city": "Jakarta",
        "country": "Indonesia",
        "continent": "Asia",
        "industry": "AI",
        "valuation": 2_000_000_000,
        "funding": 100_000_000,
        "select_investors": "East Ventures",
        "date_joined": date(2020, 5, 1),
        "year_founded": 2022,
    }

    # Act & Assert
    with pytest.raises(ValidationError, match="year_founded"):
        UnicornRecord(**payload)


def test_cohort_analysis_request_rejects_empty_records_list() -> None:
    """Explicitly passing an empty records list must fail schema validation."""
    # Arrange & Act & Assert
    with pytest.raises(ValidationError, match="at least one UnicornRecord"):
        CohortAnalysisRequest(records=[])
