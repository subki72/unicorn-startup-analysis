"""Analytics orchestration, caching, ROI computation, and non-interactive chart export."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import logging
from pathlib import Path
from threading import Lock
import time
from typing import Literal

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from unicorn_analytics.config import AnalyticsSettings  # noqa: E402
from unicorn_analytics.generator import (  # noqa: E402
    UnicornDataset,
    generate_unicorn_dataset,
    records_to_dataset,
)
from unicorn_analytics.repository import UnicornRepository  # noqa: E402
from unicorn_analytics.schemas import (  # noqa: E402
    AnalysisResponse,
    CohortAnalysisRequest,
    IndustrySummary,
    ValuationLeader,
    YearlyTrendItem,
)

logger = logging.getLogger(__name__)


def compute_roi_multiple(valuation: int, funding: int) -> float:
    """Calculate capital efficiency ROI multiple (valuation / funding).

    Args:
        valuation: Startup valuation in USD (must be > 0).
        funding: Total capital raised in USD (must be > 0).

    Returns:
        Valuation-to-funding multiple rounded to 2 decimal places.

    Raises:
        ValueError: If valuation or funding is non-positive.
    """
    if valuation <= 0:
        raise ValueError("valuation must be greater than 0")
    if funding <= 0:
        raise ValueError("funding must be greater than 0")
    return round(valuation / funding, 2)


class AnalysisCache:
    """Thread-safe bounded TTL cache for deterministic cohort analysis responses."""

    def __init__(self, max_entries: int = 64, ttl_seconds: int = 60) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be >= 0")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._entries: OrderedDict[str, tuple[float, AnalysisResponse]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> AnalysisResponse | None:
        """Retrieve a non-expired cached AnalysisResponse by key, or None."""
        if self._ttl_seconds == 0:
            return None
        now = time.monotonic()
        with self._lock:
            cached_item = self._entries.get(key)
            if cached_item is None:
                return None
            expires_at, response = cached_item
            if now >= expires_at:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return response

    def set(self, key: str, response: AnalysisResponse) -> None:
        """Store an AnalysisResponse in the bounded cache."""
        if self._ttl_seconds == 0:
            return
        expires_at = time.monotonic() + self._ttl_seconds
        with self._lock:
            self._entries[key] = (expires_at, response)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        """Evict all cached entries."""
        with self._lock:
            self._entries.clear()


def _build_cache_key(request: CohortAnalysisRequest) -> str:
    """Build a deterministic SHA-256 cache key for a CohortAnalysisRequest."""
    payload = request.model_dump_json()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_dataset(
    request: CohortAnalysisRequest,
) -> tuple[UnicornDataset, Literal["synthetic", "custom"]]:
    """Build normalized UnicornDataset from either custom payload or deterministic generator."""
    if request.records is not None:
        return records_to_dataset(request.records), "custom"
    dataset = generate_unicorn_dataset(
        num_companies=request.num_companies,
        random_seed=request.random_seed,
    )
    return dataset, "synthetic"


def run_cohort_analysis(
    request: CohortAnalysisRequest,
    settings: AnalyticsSettings,
    repo: UnicornRepository | None = None,
    cache: AnalysisCache | None = None,
) -> AnalysisResponse:
    """Execute the full ETL and SQLite analytical pipeline for a cohort request."""
    cache_key = _build_cache_key(request) if (repo is None and cache is not None) else None
    if cache_key is not None and cache is not None:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.info("Cache hit for cohort analysis key=%s", cache_key[:12])
            return cached_result.model_copy(update={"cached": True})

    dataset, source = _build_dataset(request)
    if repo is not None:
        response = _execute_queries(repo, dataset, source, request.top_n)
    else:
        with UnicornRepository(":memory:", timeout_seconds=settings.timeout_seconds) as temp_repo:
            response = _execute_queries(temp_repo, dataset, source, request.top_n)

    if cache_key is not None and cache is not None:
        cache.set(cache_key, response)

    logger.info(
        "Completed %s cohort analysis: companies=%d decacorns=%d avg_roi=%.2fx",
        source,
        response.metrics.total_companies,
        response.metrics.decacorn_count,
        response.metrics.avg_roi_multiple,
    )
    return response


def _execute_queries(
    repo: UnicornRepository,
    dataset: UnicornDataset,
    source: Literal["synthetic", "custom"],
    top_n: int,
) -> AnalysisResponse:
    """Initialize SQLite schema, persist dataset, and compile AnalysisResponse."""
    repo.initialize_schema()
    repo.replace_dataset(dataset)
    return AnalysisResponse(
        source=source,
        metrics=repo.query_summary_metrics(),
        industry_distribution=repo.query_industry_distribution(),
        top_valuations=repo.query_top_valuations(limit=top_n),
        yearly_trends=repo.query_yearly_trends(),
        cached=False,
    )


def _render_industry_chart(industries: list[IndustrySummary], dest: Path) -> Path:
    """Render and close industry distribution bar chart."""
    frame = pd.DataFrame([item.model_dump() for item in industries])
    fig, ax = plt.subplots(figsize=(10, 6))
    try:
        sns.barplot(
            data=frame,
            y="industry",
            x="total_startups",
            hue="industry",
            palette="viridis",
            legend=False,
            ax=ax,
        )
        ax.set_title("Unicorn Distribution by Industry", fontsize=14, fontweight="bold")
        ax.set_xlabel("Number of Startups")
        ax.set_ylabel("Industry Sector")
        fig.tight_layout()
        fig.savefig(dest, dpi=150)
    finally:
        plt.close(fig)
    return dest


def _render_top_valuations_chart(leaders: list[ValuationLeader], dest: Path) -> Path:
    """Render and close top unicorn valuations horizontal bar chart."""
    frame = pd.DataFrame([item.model_dump() for item in leaders])
    fig, ax = plt.subplots(figsize=(10, 6))
    try:
        sns.barplot(
            data=frame,
            x="valuation_billions",
            y="company",
            hue="company",
            palette="rocket",
            legend=False,
            ax=ax,
        )
        ax.set_title("Top Unicorns by Valuation ($ Billion)", fontsize=14, fontweight="bold")
        ax.set_xlabel("Valuation ($B)")
        ax.set_ylabel("Company Name")
        for idx, row in frame.iterrows():
            ax.text(float(row["valuation_billions"]), int(idx), f" {row['country']}", va="center")
        fig.tight_layout()
        fig.savefig(dest, dpi=150)
    finally:
        plt.close(fig)
    return dest


def _render_yearly_trends_chart(trends: list[YearlyTrendItem], dest: Path) -> Path:
    """Render and close yearly unicorn growth line chart."""
    frame = pd.DataFrame([item.model_dump() for item in trends])
    fig, ax = plt.subplots(figsize=(10, 6))
    try:
        sns.lineplot(
            data=frame,
            x="year_joined",
            y="total_new_unicorns",
            marker="o",
            linewidth=2.5,
            color="#2563eb",
            ax=ax,
        )
        ax.set_title("Growth of New Unicorns per Year", fontsize=14, fontweight="bold")
        ax.set_xlabel("Year Joined")
        ax.set_ylabel("Number of New Unicorns")
        ax.grid(True, linestyle="--", alpha=0.6)
        fig.tight_layout()
        fig.savefig(dest, dpi=150)
    finally:
        plt.close(fig)
    return dest


def export_analytics_charts(response: AnalysisResponse, output_dir: Path) -> dict[str, Path]:
    """Export non-interactive PNG analytical charts for a completed AnalysisResponse.

    Args:
        response: Completed AnalysisResponse payload.
        output_dir: Directory where PNG chart files are saved.

    Returns:
        Dictionary mapping chart name to generated PNG file path.

    Raises:
        ValueError: If response distributions are empty.
    """
    if (
        not response.industry_distribution
        or not response.top_valuations
        or not response.yearly_trends
    ):
        raise ValueError("Cannot export charts from empty analytics collections")

    output_dir.mkdir(parents=True, exist_ok=True)
    charts = {
        "industry_distribution": _render_industry_chart(
            response.industry_distribution, output_dir / "industry_distribution.png"
        ),
        "top_valuations": _render_top_valuations_chart(
            response.top_valuations, output_dir / "top_valuations.png"
        ),
        "yearly_trends": _render_yearly_trends_chart(
            response.yearly_trends, output_dir / "yearly_trends.png"
        ),
    }
    logger.info("Exported %d analytics charts to %s", len(charts), output_dir)
    return charts
