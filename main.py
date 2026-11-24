"""CLI entrypoint for executing the Unicorn Startup ETL & SQLite3 analytics pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

_SRC_DIR = str(Path(__file__).resolve().parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from unicorn_analytics.analyzer import export_analytics_charts, run_cohort_analysis  # noqa: E402
from unicorn_analytics.config import AnalyticsSettings, configure_logging  # noqa: E402
from unicorn_analytics.repository import UnicornRepository  # noqa: E402
from unicorn_analytics.schemas import CohortAnalysisRequest  # noqa: E402

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser for Unicorn Analytics."""
    parser = argparse.ArgumentParser(
        description="Run the Unicorn Startup SQLite3 ETL & valuation analytics pipeline."
    )
    parser.add_argument("--companies", type=int, default=None, help="Synthetic cohort size.")
    parser.add_argument("--seed", type=int, default=None, help="Deterministic random seed.")
    parser.add_argument("--top-n", type=int, default=5, help="Top valuation leaders count.")
    parser.add_argument("--db-path", type=str, default=None, help="SQLite path or ':memory:'.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts"),
        help="Directory for optional JSON summary and PNG chart exports.",
    )
    parser.add_argument("--export-json", action="store_true", help="Export JSON summary file.")
    parser.add_argument("--export-charts", action="store_true", help="Export PNG chart files.")
    parser.add_argument("--health", action="store_true", help="Verify SQLite schema readiness.")
    return parser


def _run_health_probe(db_path: str, timeout_seconds: float) -> int:
    """Run SQLite schema readiness verification and return shell exit code."""
    with UnicornRepository(db_path=db_path, timeout_seconds=timeout_seconds) as repo:
        repo.initialize_schema()
        ready = repo.check_health()
    if not ready:
        logger.error("Health check failed: expected tables missing in db_path=%s", db_path)
        return 1
    logger.info("Health check passed: db_path=%s schema_ready=%s", db_path, ready)
    return 0


def run_cli(argv: list[str] | None = None) -> int:
    """Execute the CLI workflow and return a standard process exit code."""
    args = build_parser().parse_args(argv)
    settings = AnalyticsSettings.from_env()
    configure_logging(settings.log_level)

    db_path = args.db_path or settings.db_path
    if args.health:
        return _run_health_probe(db_path=db_path, timeout_seconds=settings.timeout_seconds)

    num_companies = args.companies if args.companies is not None else settings.default_num_companies
    seed = args.seed if args.seed is not None else settings.random_seed
    request = CohortAnalysisRequest(num_companies=num_companies, random_seed=seed, top_n=args.top_n)

    with UnicornRepository(db_path=db_path, timeout_seconds=settings.timeout_seconds) as repo:
        result = run_cohort_analysis(request=request, settings=settings, repo=repo)

    logger.info(
        "Unicorn ETL summary: companies=%d total_valuation=$%.2fB avg_roi=%.2fx decacorns=%d",
        result.metrics.total_companies,
        result.metrics.total_valuation_billions,
        result.metrics.avg_roi_multiple,
        result.metrics.decacorn_count,
    )

    if args.export_json:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = args.output_dir / "analysis_summary.json"
        summary_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Exported analysis summary JSON to %s", summary_path)

    if args.export_charts:
        export_analytics_charts(result, args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
