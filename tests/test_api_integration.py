"""Integration tests for the FastAPI Unicorn Analytics microservice."""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import unicorn_analytics.api as api_module
from unicorn_analytics.config import AnalyticsSettings


def test_health_endpoint_returns_ok_and_security_headers() -> None:
    """GET /health should verify SQLite schema readiness and attach HTTP security headers."""
    # Arrange
    app = api_module.create_app(settings=AnalyticsSettings())
    client = TestClient(app)

    # Act
    response = client.get("/health")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db_backend"] == "sqlite3"
    assert body["schema_ready"] is True
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_analyze_synthetic_cohort_and_cache_hit() -> None:
    """POST /analyze should compute analytics and serve identical requests from cache."""
    # Arrange
    app = api_module.create_app(settings=AnalyticsSettings(cache_ttl_seconds=60))
    client = TestClient(app)
    payload = {"num_companies": 30, "random_seed": 42, "top_n": 5}

    # Act
    first = client.post("/analyze", json=payload)
    second = client.post("/analyze", json=payload)

    # Assert
    assert first.status_code == 200
    assert second.status_code == 200
    first_json = first.json()
    second_json = second.json()
    assert first_json["source"] == "synthetic"
    assert first_json["cached"] is False
    assert second_json["cached"] is True
    assert first_json["metrics"]["total_companies"] == 30
    assert len(first_json["top_valuations"]) == 5
    assert len(first_json["industry_distribution"]) >= 1
    assert len(first_json["yearly_trends"]) >= 1


def test_analyze_custom_records_returns_exact_metrics() -> None:
    """POST /analyze should process custom UnicornRecord payloads accurately."""
    # Arrange
    app = api_module.create_app(settings=AnalyticsSettings())
    client = TestClient(app)
    payload = {
        "top_n": 2,
        "records": [
            {
                "company_id": 1,
                "company": "FinEdge",
                "city": "Jakarta",
                "country": "Indonesia",
                "continent": "Asia",
                "industry": "Fintech",
                "valuation": 10_000_000_000,
                "funding": 250_000_000,
                "select_investors": "East Ventures",
                "date_joined": "2022-04-01",
                "year_founded": 2018,
            },
            {
                "company_id": 2,
                "company": "MedCloud",
                "city": "Berlin",
                "country": "Germany",
                "continent": "Europe",
                "industry": "Healthtech",
                "valuation": 2_000_000_000,
                "funding": 100_000_000,
                "select_investors": "Sequoia",
                "date_joined": "2022-08-15",
                "year_founded": 2020,
            },
        ],
    }

    # Act
    response = client.post("/analyze", json=payload)

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "custom"
    assert body["metrics"]["total_companies"] == 2
    assert body["metrics"]["total_valuation_billions"] == 12.0
    assert body["metrics"]["decacorn_count"] == 1
    assert body["top_valuations"][0]["company"] == "FinEdge"
    assert body["top_valuations"][0]["roi_multiple"] == 40.0


def test_analyze_invalid_empty_records_returns_422() -> None:
    """Empty custom records or out-of-range cohort sizes must return HTTP 422."""
    # Arrange
    app = api_module.create_app(settings=AnalyticsSettings())
    client = TestClient(app)

    # Act
    empty_resp = client.post("/analyze", json={"records": []})
    bad_size_resp = client.post("/analyze", json={"num_companies": 0})

    # Assert
    assert empty_resp.status_code == 422
    assert bad_size_resp.status_code == 422


def test_analyze_rate_limit_enforces_429_and_retry_after() -> None:
    """Sliding-window rate limiter must reject excess requests with HTTP 429 and Retry-After."""
    # Arrange
    app = api_module.create_app(settings=AnalyticsSettings(rate_limit_per_minute=2))
    client = TestClient(app)
    payload = {"num_companies": 5, "random_seed": 7, "top_n": 2}

    # Act
    r1 = client.post("/analyze", json=payload)
    r2 = client.post("/analyze", json=payload)
    r3 = client.post("/analyze", json=payload)

    # Assert
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert int(r3.headers["retry-after"]) >= 1


def test_analyze_global_exception_handler_masks_internal_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global exception handler must return generic 500 JSON without leaking stack traces."""
    # Arrange
    app = api_module.create_app(settings=AnalyticsSettings())
    client = TestClient(app, raise_server_exceptions=False)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("sensitive internal sqlite trace")

    monkeypatch.setattr(api_module, "run_cohort_analysis", _boom)

    # Act
    response = client.post("/analyze", json={"num_companies": 10})

    # Assert
    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
    assert "sensitive" not in response.text


def test_cors_allows_configured_origin_and_blocks_unlisted() -> None:
    """CORSMiddleware must only echo explicitly configured origins."""
    # Arrange
    app = api_module.create_app(
        settings=AnalyticsSettings(allowed_origins=("https://analytics.example.com",))
    )
    client = TestClient(app)

    # Act
    allowed_resp = client.get("/health", headers={"Origin": "https://analytics.example.com"})
    blocked_resp = client.get("/health", headers={"Origin": "https://evil.example.net"})

    # Assert
    assert allowed_resp.status_code == 200
    assert (
        allowed_resp.headers.get("access-control-allow-origin") == "https://analytics.example.com"
    )
    assert "access-control-allow-origin" not in blocked_resp.headers
