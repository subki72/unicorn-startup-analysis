"""Pydantic v2 request and response schemas for Unicorn Startup Analytics."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UnicornRecord(BaseModel):
    """Single normalized unicorn startup record spanning company, industry, funding, and dates."""

    model_config = ConfigDict(str_strip_whitespace=True)

    company_id: int = Field(..., ge=1, description="Unique positive identifier for the startup")
    company: str = Field(..., min_length=1, max_length=200, description="Startup legal name")
    city: str = Field(..., min_length=1, max_length=120, description="Headquarters city")
    country: str = Field(..., min_length=1, max_length=100, description="Headquarters country")
    continent: str = Field(..., min_length=1, max_length=80, description="Headquarters continent")
    industry: str = Field(..., min_length=1, max_length=80, description="Primary industry sector")
    valuation: int = Field(..., gt=0, description="Valuation in USD")
    funding: int = Field(..., gt=0, description="Total funding raised in USD")
    select_investors: str = Field(..., min_length=1, max_length=200, description="Lead investors")
    date_joined: date = Field(..., description="Date the startup reached unicorn status")
    year_founded: int = Field(..., ge=1900, le=2100, description="Year the startup was founded")

    @model_validator(mode="after")
    def validate_chronology(self) -> UnicornRecord:
        """Ensure founding year does not exceed the unicorn milestone year."""
        if self.year_founded > self.date_joined.year:
            raise ValueError(
                f"year_founded ({self.year_founded}) cannot exceed "
                f"date_joined year ({self.date_joined.year})"
            )
        return self


class CohortAnalysisRequest(BaseModel):
    """Request contract for running synthetic or custom unicorn cohort analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

    num_companies: int = Field(default=100, ge=1, le=5000, description="Synthetic cohort size")
    random_seed: int = Field(default=42, ge=0, description="Deterministic generation seed")
    top_n: int = Field(default=5, ge=1, le=50, description="Number of top valuation leaders")
    records: list[UnicornRecord] | None = Field(
        default=None,
        description="Optional custom unicorn records; overrides synthetic generation when provided",
    )

    @field_validator("records")
    @classmethod
    def validate_non_empty_records(
        cls, value: list[UnicornRecord] | None
    ) -> list[UnicornRecord] | None:
        """Reject explicitly empty record lists while allowing None for synthetic mode."""
        if value is not None and len(value) == 0:
            raise ValueError("records must contain at least one UnicornRecord when provided")
        return value


class IndustrySummary(BaseModel):
    """Aggregated startup count, valuation, and average ROI multiple per industry."""

    industry: str
    total_startups: int = Field(..., ge=1)
    total_valuation_billions: float = Field(..., gt=0.0)
    avg_roi_multiple: float = Field(..., gt=0.0)


class ValuationLeader(BaseModel):
    """Top-ranked unicorn company with valuation in billions and ROI multiple."""

    company_id: int = Field(..., ge=1)
    company: str
    country: str
    industry: str
    valuation_billions: float = Field(..., gt=0.0)
    funding_millions: float = Field(..., gt=0.0)
    roi_multiple: float = Field(..., gt=0.0)


class YearlyTrendItem(BaseModel):
    """Annual count and cumulative valuation of newly crowned unicorns."""

    year_joined: int = Field(..., ge=1900, le=2100)
    total_new_unicorns: int = Field(..., ge=1)
    total_valuation_billions: float = Field(..., gt=0.0)


class CohortMetrics(BaseModel):
    """High-level KPI summary for an analyzed unicorn cohort."""

    total_companies: int = Field(..., ge=1)
    total_valuation_billions: float = Field(..., gt=0.0)
    avg_valuation_billions: float = Field(..., gt=0.0)
    avg_roi_multiple: float = Field(..., gt=0.0)
    decacorn_count: int = Field(..., ge=0)


class AnalysisResponse(BaseModel):
    """Structured response returned by both the analytics engine and POST /analyze."""

    source: Literal["synthetic", "custom"]
    metrics: CohortMetrics
    industry_distribution: list[IndustrySummary]
    top_valuations: list[ValuationLeader]
    yearly_trends: list[YearlyTrendItem]
    cached: bool = False


class HealthResponse(BaseModel):
    """Liveness and database readiness response for GET /health."""

    status: Literal["ok"]
    service: str
    version: str
    db_backend: str
    schema_ready: bool


class ErrorResponse(BaseModel):
    """Safe external error payload without internal stack traces."""

    detail: str
    error_code: str
