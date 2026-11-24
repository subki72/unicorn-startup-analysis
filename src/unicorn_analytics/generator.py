"""Deterministic synthetic dataset generation and normalization for Unicorn Analytics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import logging
from pathlib import Path

from faker import Faker
import numpy as np
import pandas as pd

from unicorn_analytics.schemas import UnicornRecord

logger = logging.getLogger(__name__)

BILLION_USD = 1_000_000_000
MILLION_USD = 1_000_000
MAX_COHORT_SIZE = 50_000

COUNTRIES: tuple[str, ...] = (
    "United States",
    "China",
    "India",
    "UK",
    "Germany",
    "Indonesia",
    "Singapore",
    "Brazil",
)
CONTINENTS: tuple[str, ...] = (
    "North America",
    "Asia",
    "Europe",
    "South America",
)
INDUSTRIES: tuple[str, ...] = (
    "Fintech",
    "E-commerce",
    "AI",
    "Healthtech",
    "Logistics",
    "Edtech",
)
INVESTORS: tuple[str, ...] = (
    "Sequoia",
    "SoftBank",
    "Tiger Global",
    "Y Combinator",
    "East Ventures",
)

START_DATE_ISO = "2015-01-01"
END_DATE_ISO = "2023-12-31"


@dataclass(frozen=True)
class UnicornDataset:
    """Normalized four-table relational representation of unicorn startups."""

    companies: pd.DataFrame
    industries: pd.DataFrame
    funding: pd.DataFrame
    dates: pd.DataFrame

    @property
    def size(self) -> int:
        """Return total number of startups in the dataset."""
        return len(self.companies)

    def to_records(self) -> list[UnicornRecord]:
        """Convert normalized relational tables into validated UnicornRecord models."""
        merged = (
            self.companies.merge(self.industries, on="company_id")
            .merge(self.funding, on="company_id")
            .merge(self.dates, on="company_id")
        )
        return [
            UnicornRecord(
                company_id=int(row["company_id"]),
                company=str(row["company"]),
                city=str(row["city"]),
                country=str(row["country"]),
                continent=str(row["continent"]),
                industry=str(row["industry"]),
                valuation=int(row["valuation"]),
                funding=int(row["funding"]),
                select_investors=str(row["select_investors"]),
                date_joined=str(row["date_joined"]),
                year_founded=int(row["year_founded"]),
            )
            for row in merged.to_dict(orient="records")
        ]


def _build_synthetic_dates(
    rng: np.random.Generator, num_companies: int
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Generate vectorized unicorn milestone dates and chronological founding years."""
    start_ts = pd.Timestamp(START_DATE_ISO)
    end_ts = pd.Timestamp(END_DATE_ISO)
    span_days = int((end_ts - start_ts).days)
    day_offsets = rng.integers(0, span_days, size=num_companies, dtype=np.int64)
    date_joined = start_ts + pd.to_timedelta(day_offsets, unit="D")
    year_founded = date_joined.year.to_numpy(dtype=np.int64) - rng.integers(
        1, 8, size=num_companies, dtype=np.int64
    )
    return date_joined, year_founded


def _build_synthetic_dataset(num_companies: int, random_seed: int) -> UnicornDataset:
    """Populate normalized DataFrames using isolated NumPy and Faker generators."""
    rng = np.random.default_rng(random_seed)
    fake = Faker()
    fake.seed_instance(random_seed)

    company_ids = np.arange(1, num_companies + 1, dtype=np.int64)
    # Use int64 explicitly so billion-scale valuations never overflow 32-bit integers on Windows.
    valuations = rng.integers(1, 20, size=num_companies, dtype=np.int64) * BILLION_USD
    fundings = rng.integers(50, 500, size=num_companies, dtype=np.int64) * MILLION_USD
    date_joined, year_founded = _build_synthetic_dates(rng, num_companies)

    return UnicornDataset(
        companies=pd.DataFrame(
            {
                "company_id": company_ids,
                "company": [fake.company() for _ in range(num_companies)],
                "city": [fake.city() for _ in range(num_companies)],
                "country": rng.choice(COUNTRIES, size=num_companies),
                "continent": rng.choice(CONTINENTS, size=num_companies),
            }
        ),
        industries=pd.DataFrame(
            {"company_id": company_ids, "industry": rng.choice(INDUSTRIES, size=num_companies)}
        ),
        funding=pd.DataFrame(
            {
                "company_id": company_ids,
                "valuation": valuations,
                "funding": fundings,
                "select_investors": rng.choice(INVESTORS, size=num_companies),
            }
        ),
        dates=pd.DataFrame(
            {
                "company_id": company_ids,
                "date_joined": date_joined.strftime("%Y-%m-%d"),
                "year_founded": year_founded,
            }
        ),
    )


def generate_unicorn_dataset(
    num_companies: int = 100,
    random_seed: int = 42,
) -> UnicornDataset:
    """Generate a deterministic, overflow-safe relational unicorn dataset."""
    if not 1 <= num_companies <= MAX_COHORT_SIZE:
        raise ValueError(f"num_companies must be between 1 and {MAX_COHORT_SIZE}")
    if random_seed < 0:
        raise ValueError("random_seed must be non-negative")

    dataset = _build_synthetic_dataset(num_companies=num_companies, random_seed=random_seed)
    logger.info("Generated %d synthetic unicorn records with seed=%d", num_companies, random_seed)
    return dataset


def _validate_unique_records(records: Sequence[UnicornRecord]) -> None:
    """Validate that records is non-empty and contains unique company_id values."""
    if not records:
        raise ValueError("records must contain at least one UnicornRecord")
    seen_ids: set[int] = set()
    for record in records:
        if record.company_id in seen_ids:
            raise ValueError(f"Duplicate company_id detected: {record.company_id}")
        seen_ids.add(record.company_id)


def records_to_dataset(records: Sequence[UnicornRecord]) -> UnicornDataset:
    """Convert validated UnicornRecord items into a normalized UnicornDataset."""
    _validate_unique_records(records)
    rows = [
        {
            "company_id": r.company_id,
            "company": r.company,
            "city": r.city,
            "country": r.country,
            "continent": r.continent,
            "industry": r.industry,
            "valuation": r.valuation,
            "funding": r.funding,
            "select_investors": r.select_investors,
            "date_joined": r.date_joined.isoformat(),
            "year_founded": r.year_founded,
        }
        for r in records
    ]
    merged = pd.DataFrame(rows)
    logger.info("Normalized %d custom unicorn records into dataset", len(records))
    return UnicornDataset(
        companies=merged[["company_id", "company", "city", "country", "continent"]].copy(),
        industries=merged[["company_id", "industry"]].copy(),
        funding=merged[["company_id", "valuation", "funding", "select_investors"]].copy(),
        dates=merged[["company_id", "date_joined", "year_founded"]].copy(),
    )


def export_dataset_csv(dataset: UnicornDataset, output_dir: Path) -> dict[str, Path]:
    """Persist the four normalized tables as CSV files inside output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    table_frames = {
        "unicorn_companies": dataset.companies,
        "unicorn_industries": dataset.industries,
        "unicorn_funding": dataset.funding,
        "unicorn_dates": dataset.dates,
    }
    exported: dict[str, Path] = {}
    for table_name, frame in table_frames.items():
        csv_path = output_dir / f"{table_name}.csv"
        frame.to_csv(csv_path, index=False)
        exported[table_name] = csv_path
    logger.info("Exported %d CSV tables to %s", len(exported), output_dir)
    return exported
