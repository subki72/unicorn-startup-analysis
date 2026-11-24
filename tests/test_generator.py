"""Unit tests for deterministic synthetic unicorn dataset generation and CSV export."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from unicorn_analytics.generator import (
    BILLION_USD,
    MILLION_USD,
    export_dataset_csv,
    generate_unicorn_dataset,
    records_to_dataset,
)
from unicorn_analytics.schemas import UnicornRecord


def test_generate_unicorn_dataset_deterministic_and_64bit_overflow_safe() -> None:
    """Generator must be reproducible, 64-bit overflow-safe, and free of global RNG mutation."""
    # Arrange
    np.random.seed(12345)
    expected_next_global = float(np.random.random())
    np.random.seed(12345)

    # Act
    first = generate_unicorn_dataset(num_companies=50, random_seed=42)
    second = generate_unicorn_dataset(num_companies=50, random_seed=42)
    actual_next_global = float(np.random.random())

    # Assert
    assert first.size == 50
    assert first.companies.equals(second.companies)
    assert first.funding.equals(second.funding)
    assert actual_next_global == expected_next_global
    assert int(first.funding["valuation"].min()) >= BILLION_USD
    assert int(first.funding["valuation"].max()) <= 19 * BILLION_USD
    assert int(first.funding["funding"].min()) >= 50 * MILLION_USD
    joined_years = first.dates["date_joined"].str.slice(0, 4).astype(int)
    assert (first.dates["year_founded"] <= joined_years).all()


def test_generate_unicorn_dataset_rejects_invalid_bounds() -> None:
    """Out-of-range cohort size or negative seed must raise ValueError immediately."""
    # Arrange & Act & Assert
    with pytest.raises(ValueError, match="num_companies"):
        generate_unicorn_dataset(num_companies=0, random_seed=42)
    with pytest.raises(ValueError, match="num_companies"):
        generate_unicorn_dataset(num_companies=100_000, random_seed=42)
    with pytest.raises(ValueError, match="random_seed"):
        generate_unicorn_dataset(num_companies=10, random_seed=-1)


def test_records_to_dataset_roundtrip_and_duplicate_id_guard() -> None:
    """records_to_dataset should round-trip valid records and reject duplicate IDs."""
    # Arrange
    dataset = generate_unicorn_dataset(num_companies=5, random_seed=7)
    records = dataset.to_records()

    # Act
    rebuilt = records_to_dataset(records)

    # Assert
    assert rebuilt.size == 5
    assert list(rebuilt.companies["company"]) == list(dataset.companies["company"])

    duplicate = UnicornRecord(
        company_id=1,
        company="DupCo",
        city="Berlin",
        country="Germany",
        continent="Europe",
        industry="Fintech",
        valuation=2_000_000_000,
        funding=100_000_000,
        select_investors="Sequoia",
        date_joined=date(2021, 6, 15),
        year_founded=2018,
    )
    with pytest.raises(ValueError, match="Duplicate company_id"):
        records_to_dataset([duplicate, duplicate])


def test_export_dataset_csv_writes_four_tables(tmp_path: Path) -> None:
    """export_dataset_csv should persist all four normalized tables cleanly."""
    # Arrange
    dataset = generate_unicorn_dataset(num_companies=8, random_seed=11)

    # Act
    paths = export_dataset_csv(dataset, tmp_path / "csv_out")

    # Assert
    assert set(paths.keys()) == {
        "unicorn_companies",
        "unicorn_industries",
        "unicorn_funding",
        "unicorn_dates",
    }
    for csv_path in paths.values():
        assert csv_path.is_file()
        assert csv_path.stat().st_size > 0
