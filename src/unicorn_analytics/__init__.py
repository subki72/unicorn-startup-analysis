"""Modular ETL, SQLite3 persistence, and FastAPI analytics for unicorn startups."""

from unicorn_analytics.analyzer import (
    AnalysisCache,
    compute_roi_multiple,
    export_analytics_charts,
    run_cohort_analysis,
)
from unicorn_analytics.api import APP_VERSION, create_app
from unicorn_analytics.config import AnalyticsSettings, configure_logging
from unicorn_analytics.generator import (
    UnicornDataset,
    export_dataset_csv,
    generate_unicorn_dataset,
    records_to_dataset,
)
from unicorn_analytics.repository import UnicornRepository
from unicorn_analytics.schemas import (
    AnalysisResponse,
    CohortAnalysisRequest,
    CohortMetrics,
    ErrorResponse,
    HealthResponse,
    IndustrySummary,
    UnicornRecord,
    ValuationLeader,
    YearlyTrendItem,
)

__all__ = [
    "APP_VERSION",
    "AnalysisCache",
    "AnalysisResponse",
    "AnalyticsSettings",
    "CohortAnalysisRequest",
    "CohortMetrics",
    "ErrorResponse",
    "HealthResponse",
    "IndustrySummary",
    "UnicornDataset",
    "UnicornRecord",
    "UnicornRepository",
    "ValuationLeader",
    "YearlyTrendItem",
    "compute_roi_multiple",
    "configure_logging",
    "create_app",
    "export_analytics_charts",
    "export_dataset_csv",
    "generate_unicorn_dataset",
    "records_to_dataset",
    "run_cohort_analysis",
]
