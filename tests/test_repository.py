"""Unit tests for parameterized SQLite3 UnicornRepository and schema constraints."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

import pytest

from unicorn_analytics.generator import generate_unicorn_dataset, records_to_dataset
from unicorn_analytics.repository import UnicornRepository
from unicorn_analytics.schemas import UnicornRecord


def _build_sample_records() -> list[UnicornRecord]:
    """Return a deterministic three-company sample cohort for repository tests."""
    return [
        UnicornRecord(
            company_id=1,
            company="AlphaPay",
            city="New York",
            country="United States",
            continent="North America",
            industry="Fintech",
            valuation=12_000_000_000,
            funding=300_000_000,
            select_investors="Sequoia",
            date_joined=date(2021, 3, 10),
            year_founded=2016,
        ),
        UnicornRecord(
            company_id=2,
            company="BetaAI",
            city="London",
            country="UK",
            continent="Europe",
            industry="AI",
            valuation=4_000_000_000,
            funding=200_000_000,
            select_investors="SoftBank",
            date_joined=date(2022, 7, 20),
            year_founded=2019,
        ),
        UnicornRecord(
            company_id=3,
            company="GammaPay",
            city="Singapore",
            country="Singapore",
            continent="Asia",
            industry="Fintech",
            valuation=8_000_000_000,
            funding=400_000_000,
            select_investors="Tiger Global",
            date_joined=date(2021, 11, 5),
            year_founded=2017,
        ),
    ]


def test_repository_initializes_schema_and_persists_to_tmp_db(tmp_path: Path) -> None:
    """Repository should initialize schema, persist cohort to disk, and run SQL metrics."""
    # Arrange
    db_file = tmp_path / "nested" / "unicorns.db"
    dataset = records_to_dataset(_build_sample_records())

    # Act
    with UnicornRepository(db_path=str(db_file), timeout_seconds=5.0) as repo:
        repo.initialize_schema()
        inserted = repo.replace_dataset(dataset)
        healthy = repo.check_health()
        metrics = repo.query_summary_metrics()
        industries = repo.query_industry_distribution()
        leaders = repo.query_top_valuations(limit=2)
        trends = repo.query_yearly_trends()

    # Assert
    assert db_file.is_file()
    assert inserted == 3
    assert healthy is True
    assert metrics.total_companies == 3
    assert metrics.total_valuation_billions == 24.0
    assert metrics.avg_valuation_billions == 8.0
    assert metrics.decacorn_count == 1
    assert industries[0].industry == "Fintech"
    assert industries[0].total_startups == 2
    assert leaders[0].company == "AlphaPay"
    assert leaders[0].roi_multiple == 40.0
    assert len(leaders) == 2
    assert [(t.year_joined, t.total_new_unicorns) for t in trends] == [(2021, 2), (2022, 1)]


def test_repository_replace_dataset_is_idempotent(tmp_path: Path) -> None:
    """Calling replace_dataset repeatedly must replace prior rows without residual records."""
    # Arrange
    db_file = tmp_path / "idempotent.db"
    first = generate_unicorn_dataset(num_companies=10, random_seed=1)
    second = generate_unicorn_dataset(num_companies=4, random_seed=2)

    # Act
    with UnicornRepository(db_path=str(db_file)) as repo:
        repo.initialize_schema()
        repo.replace_dataset(first)
        repo.replace_dataset(second)
        metrics = repo.query_summary_metrics()

    # Assert
    assert metrics.total_companies == 4


def test_repository_enforces_foreign_keys_and_positive_constraints(tmp_path: Path) -> None:
    """SQLite schema constraints must reject orphan child rows and non-positive valuations."""
    # Arrange
    db_file = tmp_path / "constraints.db"
    with UnicornRepository(db_path=str(db_file)) as repo:
        repo.initialize_schema()

    # Act & Assert
    conn = sqlite3.connect(str(db_file), timeout=5.0)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO unicorn_funding (company_id, valuation, funding, select_investors) "
                "VALUES (999, 1000000000, 50000000, 'Sequoia')"
            )
    finally:
        conn.close()


def test_repository_query_by_country_blocks_sql_injection(tmp_path: Path) -> None:
    """Bound SQL parameters must neutralize SQL injection payloads cleanly."""
    # Arrange
    db_file = tmp_path / "sqli.db"
    dataset = generate_unicorn_dataset(num_companies=15, random_seed=42)
    with UnicornRepository(db_path=str(db_file)) as repo:
        repo.initialize_schema()
        repo.replace_dataset(dataset)

        # Act
        injected = repo.query_by_country("United States' OR '1'='1")
        legit = repo.query_by_country("United States")
        healthy = repo.check_health()

    # Assert
    assert injected == []
    assert healthy is True
    assert all(item.country == "United States" for item in legit)


def test_repository_rejects_empty_dataset_and_invalid_limit() -> None:
    """Repository guard clauses must reject invalid paths, timeouts, limits, and empty tables."""
    # Arrange
    with pytest.raises(ValueError, match="db_path"):
        UnicornRepository(db_path=" ")
    with pytest.raises(ValueError, match="timeout_seconds"):
        UnicornRepository(db_path=":memory:", timeout_seconds=0)

    with UnicornRepository(db_path=":memory:") as repo:
        repo.initialize_schema()

        # Act & Assert
        with pytest.raises(ValueError, match="limit"):
            repo.query_top_valuations(limit=0)
        with pytest.raises(ValueError, match="empty"):
            repo.query_summary_metrics()
