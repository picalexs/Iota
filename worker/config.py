"""Worker configuration."""

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.contracts.queue import DEFAULT_QUEUE_NAME
from shared.database import build_postgres_url


class WorkerSettings(BaseSettings):
    """Settings for the worker process."""

    if TYPE_CHECKING:

        def __init__(
            self,
            *,
            database_url: str = "",
            **kwargs: Any,
        ) -> None: ...

    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    redis_url: str = "redis://redis:6379/0"
    database_url: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""
    queue_name: str = DEFAULT_QUEUE_NAME
    log_level: str = "INFO"
    worker_ttl_seconds: int = 420
    redis_socket_connect_timeout_seconds: float = 5.0
    redis_socket_timeout_buffer_seconds: float = 60.0
    redis_health_check_interval_seconds: int = 30

    @model_validator(mode="after")
    def validate_required_urls(self) -> "WorkerSettings":
        """Ensure the worker has the database URL needed to persist run state."""
        if not self.database_url:
            self.database_url = self._build_database_url_from_parts()
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
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


@lru_cache
def get_settings() -> WorkerSettings:
    """Return cached worker settings."""
    return WorkerSettings()
