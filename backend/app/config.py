"""
Application configuration using Pydantic Settings v2.

Reads from environment variables and the repository-root .env file.
"""

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.enums import BackendTarget
from shared.contracts.queue import DEFAULT_QUEUE_NAME
from shared.database import build_postgres_url

_POSTGRES_SYNC_SCHEME = "postgresql://"
_POSTGRES_PSYCOPG2_SCHEME = "postgresql+psycopg2://"
_POSTGRES_ASYNCPG_SCHEME = "postgresql+asyncpg://"
_LOCAL_DEV_CORS_PORTS = ("3000", "5173")
LOCAL_DEV_DB_CREDENTIAL = "dev-password-not-secret"  # pragma: allowlist secret
LOCAL_DEV_REDIS_CREDENTIAL = "dev-redis-not-secret"  # pragma: allowlist secret


def _loopback_dev_origin(host: str, port: str) -> str:
    """Return an HTTP loopback origin for local browser development only."""
    return f"{'http'}://{host}:{port}"


def _default_cors_origins() -> str:
    origins = [
        _loopback_dev_origin(host, port)
        for host in ("localhost", "127.0.0.1")
        for port in _LOCAL_DEV_CORS_PORTS
    ]
    return ",".join(origins)


class BackendCapability:
    """Capability flags used by algorithm-aware validation."""

    def __init__(
        self,
        *,
        enabled: bool,
        supports_noise_profile: bool,
    ) -> None:
        self.enabled = enabled
        self.supports_noise_profile = supports_noise_profile


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    if TYPE_CHECKING:
        # Help static type checkers understand that Settings() can be
        # instantiated without explicit URLs, which are loaded from env.
        def __init__(
            self,
            *,
            database_url: str = "",
            redis_url: str = "",
            **kwargs: Any,
        ) -> None: ...

    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core API settings
    app_name: str = "Quantum VQE Studio API"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = ""
    database_echo: bool = False
    db_host: str = ""
    db_port: int = 5432
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""

    # Redis
    redis_url: str = ""
    queue_name: str = DEFAULT_QUEUE_NAME

    # CORS (flexible: accepts comma-separated string or JSON list)
    cors_origins: str | list[str] = _default_cors_origins()
    cors_allow_credentials: bool = False
    cors_allow_methods: str | list[str] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_allow_headers: str | list[str] = "Content-Type,Authorization,X-Local-Operator-Token"

    # Host header allowlist. Production deployments must set their public host.
    trusted_hosts: str | list[str] = "localhost,127.0.0.1"

    local_credentials_keys: str | None = None
    local_credentials_key_file: str | None = None

    # Feature flags
    skip_pubchem_sync: bool = False
    allow_insecure_defaults: bool = False
    docs_enabled: bool | None = None
    quantum_job_timeout_seconds: int = 3600
    backend_catalog_cache_seconds: int = 600
    backend_catalog_discovery_enabled: bool = True
    backend_catalog_discovery_timeout_seconds: float = 8.0

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, v: Any) -> Any:
        """Accept common runtime labels that shells sometimes expose as DEBUG."""
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"release", "prod", "production", "off", "disabled"}:
                return False
            if normalized in {"dev", "development", "on", "enabled"}:
                return True
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_cors_credentials(self) -> "Settings":
        """Disallow wildcard CORS origins with credentialed browser requests."""
        if self.cors_allow_credentials and "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS='*' cannot be combined with CORS_ALLOW_CREDENTIALS=true")
        return self

    @field_validator("cors_allow_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v: str | list[str]) -> list[str]:
        """Parse CORS methods from comma-separated string or list."""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [method.strip() for method in v.split(",") if method.strip()]
        return v

    @field_validator("cors_allow_headers", mode="before")
    @classmethod
    def parse_cors_headers(cls, v: str | list[str]) -> list[str]:
        """Parse CORS headers from comma-separated string or list."""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [header.strip() for header in v.split(",") if header.strip()]
        return v

    @field_validator("trusted_hosts", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, v: str | list[str]) -> list[str]:
        """Parse trusted Host header values from a comma-separated string."""
        if isinstance(v, str):
            return [host.strip() for host in v.split(",") if host.strip()]
        return v

    @model_validator(mode="after")
    def validate_required_urls(self) -> "Settings":
        """Ensure required infrastructure URLs are provided."""
        if not self.database_url:
            self.database_url = self._build_database_url_from_parts()
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        if not self.redis_url:
            raise ValueError("REDIS_URL is required")
        return self

    @model_validator(mode="after")
    def reject_insecure_defaults(self) -> "Settings":
        """Refuse the development placeholder password outside local development.

        Runs after validate_required_urls so the assembled DATABASE_URL is checked
        too, catching the placeholder whether it arrives via DB_PASSWORD or is
        embedded in a full connection URL.
        """
        if self.allow_insecure_defaults:
            return self
        if self.db_password == LOCAL_DEV_DB_CREDENTIAL or LOCAL_DEV_DB_CREDENTIAL in self.database_url:
            raise ValueError(
                "DB_PASSWORD is still the development placeholder. Set a real "
                "password, or set ALLOW_INSECURE_DEFAULTS=true for local use only."
            )
        if LOCAL_DEV_REDIS_CREDENTIAL in self.redis_url:
            raise ValueError(
                "REDIS_URL still carries the development placeholder credential. "
                "Set REDIS_PASSWORD to a real value, or set "
                "ALLOW_INSECURE_DEFAULTS=true for local use only."
            )
        return self

    @model_validator(mode="after")
    def resolve_docs_exposure(self) -> "Settings":
        """Default the interactive docs surface to the insecure-defaults flag.

        DOCS_ENABLED overrides it in either direction, so an operator can keep
        hardened credentials while still exposing /docs deliberately. After this
        validator the field is always a concrete boolean.
        """
        if self.docs_enabled is None:
            self.docs_enabled = self.allow_insecure_defaults
        return self

    def _build_database_url_from_parts(self) -> str:
        """Build DATABASE_URL from root .env DB_* fields when no URL is set."""
        return build_postgres_url(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.db_user,
            password=self.db_password,
        )

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Get SQLAlchemy-compatible database URI."""
        if self.database_url.startswith(_POSTGRES_SYNC_SCHEME):
            return self.database_url.replace(_POSTGRES_SYNC_SCHEME, _POSTGRES_PSYCOPG2_SCHEME, 1)
        return self.database_url

    @property
    def sqlalchemy_database_uri_async(self) -> str:
        """Get async-driver-compatible database URI (asyncpg for Postgres, aiosqlite for SQLite)."""
        if self.database_url.startswith(_POSTGRES_SYNC_SCHEME):
            return self.database_url.replace(_POSTGRES_SYNC_SCHEME, _POSTGRES_ASYNCPG_SCHEME, 1)
        if self.database_url.startswith(_POSTGRES_PSYCOPG2_SCHEME):
            return self.database_url.replace(_POSTGRES_PSYCOPG2_SCHEME, _POSTGRES_ASYNCPG_SCHEME, 1)
        if self.database_url.startswith("sqlite:///"):
            return self.database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return self.database_url

    @property
    def backend_capabilities(self) -> dict[BackendTarget, BackendCapability]:
        """Backend capability matrix for algorithm-aware validation."""
        return {
            BackendTarget.STATEVECTOR: BackendCapability(
                enabled=True,
                supports_noise_profile=False,
            ),
            BackendTarget.AER_SIMULATOR: BackendCapability(
                enabled=True,
                supports_noise_profile=True,
            ),
            BackendTarget.IBM_RUNTIME: BackendCapability(
                enabled=True,
                supports_noise_profile=False,
            ),
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
