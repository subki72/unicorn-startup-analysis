"""Environment-driven configuration and structured logging for Unicorn Analytics."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
MAX_GENERATED_COMPANIES = 50000
DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
)


def _parse_int_env(name: str, default: int) -> int:
    """Parse an integer environment variable with an explicit error context."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got {raw!r}") from exc


def _parse_float_env(name: str, default: float) -> float:
    """Parse a float environment variable with an explicit error context."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a number, got {raw!r}") from exc


def _parse_origins(raw: str | None) -> tuple[str, ...]:
    """Parse comma-separated CORS origins from environment configuration."""
    if raw is None or not raw.strip():
        return DEFAULT_ALLOWED_ORIGINS
    origins = tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())
    if not origins:
        raise ValueError("ALLOWED_ORIGINS cannot be empty when specified")
    return origins


def configure_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured leveled logging for the unicorn_analytics package.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Configured package root logger instance.

    Raises:
        ValueError: If level is not a supported Python logging level name.
    """
    normalized = level.strip().upper()
    if normalized not in VALID_LOG_LEVELS:
        raise ValueError(
            f"Unsupported LOG_LEVEL={level!r}; expected one of {sorted(VALID_LOG_LEVELS)}"
        )

    pkg_logger = logging.getLogger("unicorn_analytics")
    pkg_logger.setLevel(getattr(logging, normalized))

    if not pkg_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        pkg_logger.addHandler(handler)
        pkg_logger.propagate = False

    return pkg_logger


@dataclass(frozen=True)
class AnalyticsSettings:
    """Validated runtime settings for the Unicorn Analytics pipeline and API."""

    db_path: str = ":memory:"
    timeout_seconds: float = 10.0
    default_num_companies: int = 100
    random_seed: int = 42
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    log_level: str = "INFO"
    rate_limit_per_minute: int = 120
    cache_ttl_seconds: int = 60

    def validate(self) -> AnalyticsSettings:
        """Validate all configuration invariants and bounds.

        Returns:
            The validated AnalyticsSettings instance.

        Raises:
            ValueError: If any setting violates operational or security constraints.
        """
        if not self.db_path or not self.db_path.strip():
            raise ValueError("DB_PATH must be a non-empty path or ':memory:'")
        if self.timeout_seconds <= 0:
            raise ValueError("DB_TIMEOUT_SECONDS must be greater than 0")
        if not 1 <= self.default_num_companies <= MAX_GENERATED_COMPANIES:
            raise ValueError(
                f"DEFAULT_NUM_COMPANIES must be between 1 and {MAX_GENERATED_COMPANIES}"
            )
        if self.random_seed < 0:
            raise ValueError("RANDOM_SEED must be non-negative")
        if self.log_level.strip().upper() not in VALID_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(VALID_LOG_LEVELS)}")
        if self.rate_limit_per_minute < 1:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be >= 1")
        if self.cache_ttl_seconds < 0:
            raise ValueError("CACHE_TTL_SECONDS must be >= 0")

        for origin in self.allowed_origins:
            if origin == "*" or not origin.startswith(("http://", "https://")):
                raise ValueError(
                    f"Invalid ALLOWED_ORIGINS entry {origin!r}; explicit http(s) origin required"
                )
        return self

    @classmethod
    def from_env(cls, env_file: Path | str | None = None) -> AnalyticsSettings:
        """Load and validate AnalyticsSettings from environment variables.

        Args:
            env_file: Optional path to a dotenv file; existing OS vars take precedence.

        Returns:
            A validated AnalyticsSettings instance.
        """
        if env_file is not None:
            load_dotenv(dotenv_path=Path(env_file), override=False)

        settings = cls(
            db_path=os.getenv("DB_PATH", ":memory:").strip(),
            timeout_seconds=_parse_float_env("DB_TIMEOUT_SECONDS", 10.0),
            default_num_companies=_parse_int_env("DEFAULT_NUM_COMPANIES", 100),
            random_seed=_parse_int_env("RANDOM_SEED", 42),
            allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS")),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            rate_limit_per_minute=_parse_int_env("RATE_LIMIT_PER_MINUTE", 120),
            cache_ttl_seconds=_parse_int_env("CACHE_TTL_SECONDS", 60),
        )
        logger.debug("Loaded AnalyticsSettings for db_path=%s", settings.db_path)
        return settings.validate()
