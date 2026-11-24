"""FastAPI microservice exposing unicorn cohort analytics and liveness probes."""

from __future__ import annotations

from collections import defaultdict, deque
import logging
from threading import Lock
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from unicorn_analytics.analyzer import AnalysisCache, run_cohort_analysis
from unicorn_analytics.config import AnalyticsSettings, configure_logging
from unicorn_analytics.repository import UnicornRepository
from unicorn_analytics.schemas import (
    AnalysisResponse,
    CohortAnalysisRequest,
    ErrorResponse,
    HealthResponse,
)

logger = logging.getLogger(__name__)

APP_VERSION = "1.0.0"
SERVICE_NAME = "unicorn-startup-analysis"


class SlidingWindowRateLimiter:
    """Thread-safe in-memory per-client sliding-window HTTP rate limiter."""

    def __init__(self, max_requests: int, window_seconds: float = 60.0) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check_allowed(self, client_id: str) -> tuple[bool, int]:
        """Check whether client_id is within its request quota."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._buckets[client_id]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - timestamps[0])) + 1)
                return False, retry_after
            timestamps.append(now)
            return True, 0


def _extract_client_key(request: Request) -> str:
    """Resolve stable client identifier for rate limiting without trusting spoofed headers."""
    if request.client is not None and request.client.host:
        return request.client.host
    return "local-client"


def _configure_security(api: FastAPI, settings: AnalyticsSettings) -> None:
    """Attach CORS allowlist, HTTP security headers, and global exception masking."""
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Accept"],
    )

    @api.middleware("http")
    async def attach_security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        payload = ErrorResponse(detail="Internal server error", error_code="INTERNAL_ERROR")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload.model_dump(),
        )


def _register_routes(
    api: FastAPI,
    settings: AnalyticsSettings,
    cache: AnalysisCache,
    rate_limiter: SlidingWindowRateLimiter,
) -> None:
    """Register liveness health check and cohort analytics API endpoints."""

    @api.get("/health", response_model=HealthResponse, tags=["Operations"])
    def health_check() -> HealthResponse:
        """Liveness and SQLite schema readiness probe."""
        with UnicornRepository(":memory:", timeout_seconds=settings.timeout_seconds) as repo:
            repo.initialize_schema()
            ready = repo.check_health()
        logger.info("Health probe checked: schema_ready=%s", ready)
        return HealthResponse(
            status="ok",
            service=SERVICE_NAME,
            version=APP_VERSION,
            db_backend="sqlite3",
            schema_ready=ready,
        )

    @api.post("/analyze", response_model=AnalysisResponse, tags=["Analytics"])
    def analyze_cohort(payload: CohortAnalysisRequest, request: Request) -> AnalysisResponse:
        """Run synthetic or custom unicorn cohort analysis through SQLite3 analytics."""
        allowed, retry_after = rate_limiter.check_allowed(_extract_client_key(request))
        if not allowed:
            logger.warning("Rate limit exceeded for client=%s", _extract_client_key(request))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded; please retry shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        return run_cohort_analysis(request=payload, settings=settings, cache=cache)


def create_app(
    settings: AnalyticsSettings | None = None,
    cache: AnalysisCache | None = None,
) -> FastAPI:
    """Create and configure the FastAPI Unicorn Analytics microservice."""
    active_settings = (settings or AnalyticsSettings.from_env()).validate()
    configure_logging(active_settings.log_level)

    active_cache = cache or AnalysisCache(
        max_entries=64,
        ttl_seconds=active_settings.cache_ttl_seconds,
    )
    rate_limiter = SlidingWindowRateLimiter(
        max_requests=active_settings.rate_limit_per_minute,
        window_seconds=60.0,
    )

    api = FastAPI(
        title="Unicorn Startup Analytics API",
        version=APP_VERSION,
        description="Modular SQLite3 ETL & valuation analytics microservice.",
    )
    api.state.settings = active_settings
    api.state.cache = active_cache
    api.state.rate_limiter = rate_limiter

    _configure_security(api, active_settings)
    _register_routes(api, active_settings, active_cache, rate_limiter)
    return api


app = create_app()
