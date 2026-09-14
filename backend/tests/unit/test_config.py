"""
Unit tests for application configuration (Settings).
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from app.config import (
    LOCAL_DEV_DB_CREDENTIAL,
    LOCAL_DEV_REDIS_CREDENTIAL,
    Settings,
    get_settings,
)
from app.models.enums import BackendTarget
from pydantic import ValidationError


class TestSettingsBasics:
    """Test basic Settings configuration."""

    def test_settings_defaults(self):
        """Test that default values are applied correctly."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

            assert settings.app_name == "Quantum VQE Studio API"
            assert settings.app_version
            assert settings.debug is False
            assert settings.log_level == "INFO"
            assert settings.queue_name == "quantum"

    def test_settings_custom_values(self):
        """Test that custom environment values override defaults."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/custom_db",
                "REDIS_URL": "redis://localhost:6379/1",
                "DEBUG": "true",
                "LOG_LEVEL": "DEBUG",
                "APP_NAME": "Custom App",
                "QUEUE_NAME": "custom-queue",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.app_name == "Custom App"
            assert settings.debug is True
            assert settings.log_level == "DEBUG"
            assert settings.queue_name == "custom-queue"

    def test_settings_accepts_runtime_debug_labels(self):
        """Test that ambient runtime labels do not break DEBUG parsing."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "DEBUG": "release",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

            assert settings.debug is False

    def test_settings_required_database_url(self):
        """Test that DATABASE_URL is required."""
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0"}, clear=True):
            with pytest.raises(ValidationError):
                Settings(_env_file=None)

    def test_settings_required_redis_url(self):
        """Test that REDIS_URL is required."""
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://localhost:5432/testdb"},
            clear=True,
        ):
            with pytest.raises(ValidationError):
                Settings(_env_file=None)


class TestCORSOriginsParsing:
    """Test CORS origins parsing from comma-separated string or list."""

    def test_cors_origins_comma_separated_string(self):
        """Test parsing comma-separated CORS origins."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173,https://example.com",
            },
            clear=False,
        ):
            settings = Settings()

            assert isinstance(settings.cors_origins, list)
            assert len(settings.cors_origins) == 3
            assert "http://localhost:3000" in settings.cors_origins
            assert "http://localhost:5173" in settings.cors_origins
            assert "https://example.com" in settings.cors_origins

    def test_cors_origins_default(self):
        """Test default CORS origins."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
            },
            clear=False,
        ):
            os.environ.pop("CORS_ORIGINS", None)
            settings = Settings()

            assert isinstance(settings.cors_origins, list)
            assert "http://localhost:3000" in settings.cors_origins
            assert "http://localhost:5173" in settings.cors_origins
            assert "http://127.0.0.1:3000" in settings.cors_origins
            assert "http://127.0.0.1:5173" in settings.cors_origins

    def test_cors_origins_wildcard(self):
        """Test CORS origins wildcard '*' without credentialed requests."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ORIGINS": "*",
                "CORS_ALLOW_CREDENTIALS": "false",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.cors_origins == ["*"]
            assert settings.cors_allow_credentials is False

    def test_cors_wildcard_rejects_credentials(self):
        """Test wildcard CORS origins cannot be combined with credentials."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ORIGINS": "*",
                "CORS_ALLOW_CREDENTIALS": "true",
            },
            clear=False,
        ):
            with pytest.raises(ValidationError, match="CORS_ORIGINS"):
                Settings()

    def test_cors_origins_list(self):
        """Test CORS origins as list (Pydantic coercion)."""
        origins = ["http://localhost:3000", "https://example.com"]
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
            },
            clear=False,
        ):
            settings = Settings(cors_origins=origins)

            assert settings.cors_origins == origins

    def test_cors_origins_whitespace_trimmed(self):
        """Test that whitespace is trimmed from CORS origins."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ORIGINS": "  http://localhost:3000  ,  https://example.com  ",
            },
            clear=False,
        ):
            settings = Settings()

            assert "http://localhost:3000" in settings.cors_origins
            assert "https://example.com" in settings.cors_origins
            # Ensure no whitespace-only entries
            assert all(origin.strip() == origin for origin in settings.cors_origins)


class TestCORSMethodsParsing:
    """Test CORS methods parsing."""

    def test_cors_allow_methods_comma_separated(self):
        """Test parsing comma-separated CORS methods."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ALLOW_METHODS": "GET,POST,PUT,DELETE",
            },
            clear=False,
        ):
            settings = Settings()

            assert isinstance(settings.cors_allow_methods, list)
            assert "GET" in settings.cors_allow_methods
            assert "POST" in settings.cors_allow_methods

    def test_cors_allow_methods_wildcard(self):
        """Test CORS methods wildcard '*'."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ALLOW_METHODS": "*",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.cors_allow_methods == ["*"]


class TestCORSHeadersParsing:
    """Test CORS headers parsing."""

    def test_cors_allow_headers_comma_separated(self):
        """Test parsing comma-separated CORS headers."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ALLOW_HEADERS": "Content-Type,Authorization,X-Custom-Header",
            },
            clear=False,
        ):
            settings = Settings()

            assert isinstance(settings.cors_allow_headers, list)
            assert "Content-Type" in settings.cors_allow_headers
            assert "Authorization" in settings.cors_allow_headers

    def test_cors_allow_headers_wildcard(self):
        """Test CORS headers wildcard '*'."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
                "CORS_ALLOW_HEADERS": "*",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.cors_allow_headers == ["*"]


class TestDatabaseURL:
    """Test database URL handling."""

    def test_database_url_postgresql_conversion(self):
        """Test that postgresql:// is converted to postgresql+psycopg2://."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.sqlalchemy_database_uri.startswith("postgresql+psycopg2://")

    def test_database_url_already_psycopg2(self):
        """Test that postgresql+psycopg2:// URLs are left unchanged."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+psycopg2://localhost:5432/testdb",
                "REDIS_URL": "redis://localhost:6379/0",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.sqlalchemy_database_uri == "postgresql+psycopg2://localhost:5432/testdb"

    def test_database_url_sqlite(self):
        """Test SQLite database URLs are handled correctly."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "sqlite:///./test.db",
                "REDIS_URL": "redis://localhost:6379/0",
            },
            clear=False,
        ):
            settings = Settings()

            assert settings.sqlalchemy_database_uri == "sqlite:///./test.db"

    def test_database_url_can_be_derived_from_root_db_fields(self):
        """Test root .env DB_* fields can replace a folder-local DATABASE_URL."""
        db_credential = "local-db:@credential"
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "db",
                "DB_PORT": "5432",
                "DB_NAME": "vqe",
                "DB_USER": "vqe",
                "DB_PASSWORD": db_credential,
                "REDIS_URL": "redis://localhost:6379/0",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)

            assert settings.database_url == "postgresql://vqe:local-db%3A%40credential@db:5432/vqe"
            assert settings.sqlalchemy_database_uri.startswith("postgresql+psycopg2://")


def test_backend_capabilities_matrix() -> None:
    with patch.dict(
        os.environ,
        {
            "DATABASE_URL": "postgresql://localhost:5432/testdb",
            "REDIS_URL": "redis://localhost:6379/0",
        },
        clear=False,
    ):
        settings = Settings()

        capabilities = settings.backend_capabilities

        assert capabilities[BackendTarget.STATEVECTOR].enabled is True
        assert capabilities[BackendTarget.STATEVECTOR].supports_noise_profile is False
        assert capabilities[BackendTarget.AER_SIMULATOR].enabled is True
        assert capabilities[BackendTarget.AER_SIMULATOR].supports_noise_profile is True
        assert capabilities[BackendTarget.IBM_RUNTIME].enabled is True
        assert capabilities[BackendTarget.IBM_RUNTIME].supports_noise_profile is False


class TestGetSettingsCaching:
    """Test get_settings caching functionality."""

    def test_get_settings_returns_settings(self):
        """Test that get_settings returns a Settings instance."""
        # Clear the cache first
        get_settings.cache_clear()

        settings = get_settings()

        assert isinstance(settings, Settings)

    def test_get_settings_caches_result(self):
        """Test that get_settings caches the result."""
        # Clear the cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the exact same instance due to caching
        assert settings1 is settings2


class TestInsecureDefaultsGuard:
    """Tests for the placeholder-credential guard and docs exposure gate."""

    def test_placeholder_password_allowed_by_default(self):
        """Local development keeps working with the checked-in placeholder."""
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "db",
                "DB_NAME": "vqe",
                "DB_USER": "vqe",
                "DB_PASSWORD": LOCAL_DEV_DB_CREDENTIAL,
                "REDIS_URL": "redis://localhost:6379/0",
                "DATABASE_URL": "",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

            assert settings.allow_insecure_defaults is True
            assert settings.docs_enabled is True

    def test_placeholder_password_rejected_when_insecure_defaults_disabled(self):
        """Hardened deployments must not run on the development password."""
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "db",
                "DB_NAME": "vqe",
                "DB_USER": "vqe",
                "DB_PASSWORD": LOCAL_DEV_DB_CREDENTIAL,
                "REDIS_URL": "redis://localhost:6379/0",
                "DATABASE_URL": "",
                "ALLOW_INSECURE_DEFAULTS": "false",
            },
            clear=False,
        ):
            with pytest.raises(ValidationError, match="DB_PASSWORD"):
                Settings(_env_file=None)

    def test_placeholder_inside_database_url_is_rejected(self):
        """The guard must also catch the placeholder embedded in DATABASE_URL."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": f"postgresql://vqe:{LOCAL_DEV_DB_CREDENTIAL}@db:5432/vqe",
                "REDIS_URL": "redis://localhost:6379/0",
                "ALLOW_INSECURE_DEFAULTS": "false",
            },
            clear=False,
        ):
            with pytest.raises(ValidationError, match="DB_PASSWORD"):
                Settings(_env_file=None)

    def test_real_password_accepted_when_insecure_defaults_disabled(self):
        """A genuine password passes the guard."""
        with patch.dict(
            os.environ,
            {
                "DB_HOST": "db",
                "DB_NAME": "vqe",
                "DB_USER": "vqe",
                "DB_PASSWORD": "an-actual-password",
                "REDIS_URL": "redis://localhost:6379/0",
                "DATABASE_URL": "",
                "ALLOW_INSECURE_DEFAULTS": "false",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

            assert settings.allow_insecure_defaults is False

    def test_placeholder_redis_credential_rejected_when_hardened(self):
        """The queue credential must not stay on the development placeholder."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://vqe:real-password@db:5432/vqe",
                "DB_PASSWORD": "real-password",
                "REDIS_URL": f"redis://:{LOCAL_DEV_REDIS_CREDENTIAL}@redis:6379/0",
                "ALLOW_INSECURE_DEFAULTS": "false",
            },
            clear=False,
        ):
            with pytest.raises(ValidationError, match="REDIS_URL"):
                Settings(_env_file=None)

    def test_docs_disabled_when_insecure_defaults_disabled(self):
        """Hardened deployments drop the interactive docs surface by default."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://vqe:real-password@db:5432/vqe",
                "DB_PASSWORD": "real-password",
                "REDIS_URL": "redis://localhost:6379/0",
                "ALLOW_INSECURE_DEFAULTS": "false",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

            assert settings.docs_enabled is False

    def test_docs_can_be_re_enabled_explicitly(self):
        """An operator can opt back into docs without re-enabling other defaults."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql://vqe:real-password@db:5432/vqe",
                "DB_PASSWORD": "real-password",
                "REDIS_URL": "redis://localhost:6379/0",
                "ALLOW_INSECURE_DEFAULTS": "false",
                "DOCS_ENABLED": "true",
            },
            clear=False,
        ):
            settings = Settings(_env_file=None)

            assert settings.docs_enabled is True
