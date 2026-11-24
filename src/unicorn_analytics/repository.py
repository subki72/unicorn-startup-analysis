"""Parameterized SQLite3 repository and schema migration manager."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import logging
from pathlib import Path
import sqlite3
from types import TracebackType

from unicorn_analytics.generator import BILLION_USD, MILLION_USD, UnicornDataset
from unicorn_analytics.schemas import (
    CohortMetrics,
    IndustrySummary,
    ValuationLeader,
    YearlyTrendItem,
)

logger = logging.getLogger(__name__)

DEFAULT_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "migrations" / "001_unicorn_schema.sql"
)
EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        "unicorn_companies",
        "unicorn_industries",
        "unicorn_funding",
        "unicorn_dates",
    }
)
DECACORN_THRESHOLD_USD = 10 * BILLION_USD


def _extract_table_tuples(
    dataset: UnicornDataset,
) -> tuple[
    list[tuple[object, ...]],
    list[tuple[object, ...]],
    list[tuple[object, ...]],
    list[tuple[object, ...]],
]:
    """Convert normalized DataFrames into tuple batches for parameterized SQLite inserts."""
    company_rows = list(
        dataset.companies[["company_id", "company", "city", "country", "continent"]].itertuples(
            index=False, name=None
        )
    )
    industry_rows = list(
        dataset.industries[["company_id", "industry"]].itertuples(index=False, name=None)
    )
    funding_rows = list(
        dataset.funding[["company_id", "valuation", "funding", "select_investors"]].itertuples(
            index=False, name=None
        )
    )
    date_rows = list(
        dataset.dates[["company_id", "date_joined", "year_founded"]].itertuples(
            index=False, name=None
        )
    )
    return company_rows, industry_rows, funding_rows, date_rows


class UnicornRepository:
    """Parameterized SQLite3 persistence and analytical query layer."""

    def __init__(
        self,
        db_path: str = ":memory:",
        timeout_seconds: float = 10.0,
        migration_path: Path | None = None,
    ) -> None:
        """Initialize repository connection configuration.

        Args:
            db_path: SQLite database path or ':memory:'.
            timeout_seconds: SQLite lock wait timeout in seconds.
            migration_path: Optional override path for SQL schema migration file.

        Raises:
            ValueError: If db_path is empty or timeout_seconds <= 0.
        """
        if not db_path or not db_path.strip():
            raise ValueError("db_path must be non-empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        self.db_path = db_path.strip()
        self.timeout_seconds = timeout_seconds
        self.migration_path = migration_path or DEFAULT_MIGRATION_PATH
        self._memory_conn: sqlite3.Connection | None = None

    def __enter__(self) -> UnicornRepository:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close any persistent in-memory SQLite connection cleanly."""
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        """Yield a transaction-scoped SQLite connection with FK enforcement and timeout."""
        if self.db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(
                    ":memory:",
                    timeout=self.timeout_seconds,
                    check_same_thread=False,
                )
            conn = self._memory_conn
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            return

        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_file), timeout=self.timeout_seconds)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Apply the versioned SQL migration script to create normalized tables and indexes."""
        if not self.migration_path.is_file():
            raise FileNotFoundError(f"Migration SQL file not found: {self.migration_path}")
        ddl = self.migration_path.read_text(encoding="utf-8")
        with self._session() as conn:
            conn.executescript(ddl)
        logger.info("Initialized SQLite schema from %s", self.migration_path.name)

    def replace_dataset(self, dataset: UnicornDataset) -> int:
        """Atomically replace all unicorn cohort rows with the supplied dataset."""
        if dataset.size == 0:
            raise ValueError("Cannot persist an empty UnicornDataset")

        company_rows, industry_rows, funding_rows, date_rows = _extract_table_tuples(dataset)
        with self._session() as conn:
            for table_name in (
                "unicorn_dates",
                "unicorn_funding",
                "unicorn_industries",
                "unicorn_companies",
            ):
                conn.execute(f"DELETE FROM {table_name}")  # noqa: S608

            conn.executemany(
                "INSERT INTO unicorn_companies "
                "(company_id, company, city, country, continent) VALUES (?, ?, ?, ?, ?)",
                company_rows,
            )
            conn.executemany(
                "INSERT INTO unicorn_industries (company_id, industry) VALUES (?, ?)",
                industry_rows,
            )
            conn.executemany(
                "INSERT INTO unicorn_funding "
                "(company_id, valuation, funding, select_investors) VALUES (?, ?, ?, ?)",
                funding_rows,
            )
            conn.executemany(
                "INSERT INTO unicorn_dates (company_id, date_joined, year_founded) "
                "VALUES (?, ?, ?)",
                date_rows,
            )

        logger.info("Persisted %d unicorn records to SQLite", dataset.size)
        return dataset.size

    def check_health(self) -> bool:
        """Verify database connectivity and presence of all four normalized tables."""
        with self._session() as conn:
            conn.execute("SELECT 1").fetchone()
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        existing = {str(row["name"]) for row in rows}
        return EXPECTED_TABLES.issubset(existing)

    def query_industry_distribution(self) -> list[IndustrySummary]:
        """Aggregate startup counts, total valuation ($B), and average ROI by industry."""
        sql = """
        SELECT
            ui.industry AS industry,
            COUNT(uc.company_id) AS total_startups,
            ROUND(SUM(CAST(uf.valuation AS REAL)) / ?, 2) AS total_valuation_billions,
            ROUND(AVG(CAST(uf.valuation AS REAL) / uf.funding), 2) AS avg_roi_multiple
        FROM unicorn_companies uc
        JOIN unicorn_industries ui ON uc.company_id = ui.company_id
        JOIN unicorn_funding uf ON uc.company_id = uf.company_id
        GROUP BY ui.industry
        ORDER BY total_startups DESC, total_valuation_billions DESC, ui.industry ASC
        """
        with self._session() as conn:
            rows = conn.execute(sql, (BILLION_USD,)).fetchall()
        return [
            IndustrySummary(
                industry=str(row["industry"]),
                total_startups=int(row["total_startups"]),
                total_valuation_billions=float(row["total_valuation_billions"]),
                avg_roi_multiple=float(row["avg_roi_multiple"]),
            )
            for row in rows
        ]

    def query_top_valuations(self, limit: int = 5) -> list[ValuationLeader]:
        """Fetch top-N unicorn startups ordered by valuation descending."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")

        sql = """
        SELECT
            uc.company_id AS company_id,
            uc.company AS company,
            uc.country AS country,
            ui.industry AS industry,
            ROUND(CAST(uf.valuation AS REAL) / ?, 2) AS valuation_billions,
            ROUND(CAST(uf.funding AS REAL) / ?, 2) AS funding_millions,
            ROUND(CAST(uf.valuation AS REAL) / uf.funding, 2) AS roi_multiple
        FROM unicorn_companies uc
        JOIN unicorn_industries ui ON uc.company_id = ui.company_id
        JOIN unicorn_funding uf ON uc.company_id = uf.company_id
        ORDER BY uf.valuation DESC, uc.company_id ASC
        LIMIT ?
        """
        with self._session() as conn:
            rows = conn.execute(sql, (BILLION_USD, MILLION_USD, limit)).fetchall()
        return [
            ValuationLeader(
                company_id=int(row["company_id"]),
                company=str(row["company"]),
                country=str(row["country"]),
                industry=str(row["industry"]),
                valuation_billions=float(row["valuation_billions"]),
                funding_millions=float(row["funding_millions"]),
                roi_multiple=float(row["roi_multiple"]),
            )
            for row in rows
        ]

    def query_by_country(self, country: str) -> list[ValuationLeader]:
        """Safely query startups filtered by exact country name using bound parameters."""
        normalized = country.strip()
        if not normalized:
            raise ValueError("country filter must be non-empty")

        sql = """
        SELECT
            uc.company_id AS company_id,
            uc.company AS company,
            uc.country AS country,
            ui.industry AS industry,
            ROUND(CAST(uf.valuation AS REAL) / ?, 2) AS valuation_billions,
            ROUND(CAST(uf.funding AS REAL) / ?, 2) AS funding_millions,
            ROUND(CAST(uf.valuation AS REAL) / uf.funding, 2) AS roi_multiple
        FROM unicorn_companies uc
        JOIN unicorn_industries ui ON uc.company_id = ui.company_id
        JOIN unicorn_funding uf ON uc.company_id = uf.company_id
        WHERE uc.country = ?
        ORDER BY uf.valuation DESC, uc.company_id ASC
        """
        with self._session() as conn:
            rows = conn.execute(sql, (BILLION_USD, MILLION_USD, normalized)).fetchall()
        return [
            ValuationLeader(
                company_id=int(row["company_id"]),
                company=str(row["company"]),
                country=str(row["country"]),
                industry=str(row["industry"]),
                valuation_billions=float(row["valuation_billions"]),
                funding_millions=float(row["funding_millions"]),
                roi_multiple=float(row["roi_multiple"]),
            )
            for row in rows
        ]

    def query_yearly_trends(self) -> list[YearlyTrendItem]:
        """Aggregate yearly count and total valuation of newly crowned unicorns."""
        sql = """
        SELECT
            CAST(substr(ud.date_joined, 1, 4) AS INTEGER) AS year_joined,
            COUNT(uc.company_id) AS total_new_unicorns,
            ROUND(SUM(CAST(uf.valuation AS REAL)) / ?, 2) AS total_valuation_billions
        FROM unicorn_companies uc
        JOIN unicorn_dates ud ON uc.company_id = ud.company_id
        JOIN unicorn_funding uf ON uc.company_id = uf.company_id
        GROUP BY year_joined
        ORDER BY year_joined ASC
        """
        with self._session() as conn:
            rows = conn.execute(sql, (BILLION_USD,)).fetchall()
        return [
            YearlyTrendItem(
                year_joined=int(row["year_joined"]),
                total_new_unicorns=int(row["total_new_unicorns"]),
                total_valuation_billions=float(row["total_valuation_billions"]),
            )
            for row in rows
        ]

    def query_summary_metrics(self) -> CohortMetrics:
        """Compute cohort-wide valuation, ROI, and decacorn summary metrics."""
        sql = """
        SELECT
            COUNT(uc.company_id) AS total_companies,
            ROUND(SUM(CAST(uf.valuation AS REAL)) / ?, 2) AS total_valuation_billions,
            ROUND(AVG(CAST(uf.valuation AS REAL)) / ?, 2) AS avg_valuation_billions,
            ROUND(AVG(CAST(uf.valuation AS REAL) / uf.funding), 2) AS avg_roi_multiple,
            SUM(CASE WHEN uf.valuation >= ? THEN 1 ELSE 0 END) AS decacorn_count
        FROM unicorn_companies uc
        JOIN unicorn_funding uf ON uc.company_id = uf.company_id
        """
        with self._session() as conn:
            row = conn.execute(sql, (BILLION_USD, BILLION_USD, DECACORN_THRESHOLD_USD)).fetchone()

        if row is None or int(row["total_companies"]) == 0:
            raise ValueError("Cannot compute cohort metrics on an empty database")

        return CohortMetrics(
            total_companies=int(row["total_companies"]),
            total_valuation_billions=float(row["total_valuation_billions"]),
            avg_valuation_billions=float(row["avg_valuation_billions"]),
            avg_roi_multiple=float(row["avg_roi_multiple"]),
            decacorn_count=int(row["decacorn_count"]),
        )
