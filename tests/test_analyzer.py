"""Unit tests for ROI analytics, TTL caching, PNG chart export, and CLI runner."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest

import main as cli_main
from unicorn_analytics.analyzer import (
    AnalysisCache,
    compute_roi_multiple,
    export_analytics_charts,
    run_cohort_analysis,
)
from unicorn_analytics.config import AnalyticsSettings
from unicorn_analytics.repository import UnicornRepository
from unicorn_analytics.schemas import CohortAnalysisRequest, UnicornRecord


def test_compute_roi_multiple_happy_path_and_guards() -> None:
    """ROI calculator should compute valuation/funding ratio and reject non-positive inputs."""
    # Arrange & Act
    roi = compute_roi_multiple(valuation=10_000_000_000, funding=250_000_000)

    # Assert
    assert roi == 40.0
    with pytest.raises(ValueError, match="valuation"):
        compute_roi_multiple(valuation=0, funding=100_000_000)
    with pytest.raises(ValueError, match="funding"):
        compute_roi_multiple(valuation=1_000_000_000, funding=-5)


def test_run_cohort_analysis_synthetic_and_custom_records(tmp_path: Path) -> None:
    """run_cohort_analysis should support both synthetic cohorts and custom records."""
    # Arrange
    settings = AnalyticsSettings(db_path=str(tmp_path / "analytics.db"), timeout_seconds=5.0)
    custom_record = UnicornRecord(
        company_id=1,
        company="NusantaraAI",
        city="Jakarta",
        country="Indonesia",
        continent="Asia",
        industry="AI",
        valuation=15_000_000_000,
        funding=500_000_000,
        select_investors="East Ventures",
        date_joined=date(2023, 2, 1),
        year_founded=2019,
    )
    custom_req = CohortAnalysisRequest(top_n=3, records=[custom_record])

    # Act
    with UnicornRepository(db_path=settings.db_path, timeout_seconds=5.0) as repo:
        custom_resp = run_cohort_analysis(request=custom_req, settings=settings, repo=repo)
    synthetic_resp = run_cohort_analysis(
        request=CohortAnalysisRequest(num_companies=20, random_seed=42, top_n=5),
        settings=AnalyticsSettings(),
    )

    # Assert
    assert custom_resp.source == "custom"
    assert custom_resp.metrics.total_companies == 1
    assert custom_resp.metrics.decacorn_count == 1
    assert custom_resp.top_valuations[0].roi_multiple == 30.0
    assert synthetic_resp.source == "synthetic"
    assert synthetic_resp.metrics.total_companies == 20
    assert len(synthetic_resp.top_valuations) == 5


def test_analysis_cache_returns_cached_response_and_expires() -> None:
    """AnalysisCache should serve warm hits and evict entries past max_entries."""
    # Arrange
    cache = AnalysisCache(max_entries=1, ttl_seconds=60)
    settings = AnalyticsSettings()
    req_one = CohortAnalysisRequest(num_companies=10, random_seed=1, top_n=3)
    req_two = CohortAnalysisRequest(num_companies=10, random_seed=2, top_n=3)

    # Act
    first = run_cohort_analysis(req_one, settings=settings, cache=cache)
    second = run_cohort_analysis(req_one, settings=settings, cache=cache)
    third = run_cohort_analysis(req_two, settings=settings, cache=cache)
    fourth = run_cohort_analysis(req_one, settings=settings, cache=cache)

    # Assert
    assert first.cached is False
    assert second.cached is True
    assert third.cached is False
    assert fourth.cached is False


def test_export_analytics_charts_creates_three_png_files(tmp_path: Path) -> None:
    """Chart exporter should render three closed non-interactive PNG files."""
    # Arrange
    settings = AnalyticsSettings()
    response = run_cohort_analysis(
        CohortAnalysisRequest(num_companies=25, random_seed=42, top_n=5),
        settings=settings,
    )

    # Act
    chart_paths = export_analytics_charts(response, tmp_path / "charts")

    # Assert
    assert set(chart_paths.keys()) == {
        "industry_distribution",
        "top_valuations",
        "yearly_trends",
    }
    for png_path in chart_paths.values():
        assert png_path.is_file()
        assert png_path.stat().st_size > 1000


def test_cli_run_health_and_exports(tmp_path: Path) -> None:
    """CLI entrypoint should pass --health check and export JSON + charts cleanly."""
    # Arrange
    db_file = tmp_path / "cli_unicorns.db"
    out_dir = tmp_path / "cli_out"

    # Act
    health_code = cli_main.run_cli(["--db-path", str(db_file), "--health"])
    run_code = cli_main.run_cli(
        [
            "--companies",
            "15",
            "--seed",
            "42",
            "--top-n",
            "5",
            "--db-path",
            str(db_file),
            "--output-dir",
            str(out_dir),
            "--export-json",
            "--export-charts",
        ]
    )

    # Assert
    assert health_code == 0
    assert run_code == 0
    summary_file = out_dir / "analysis_summary.json"
    assert summary_file.is_file()
    payload = json.loads(summary_file.read_text(encoding="utf-8"))
    assert payload["metrics"]["total_companies"] == 15
    assert (out_dir / "industry_distribution.png").is_file()
