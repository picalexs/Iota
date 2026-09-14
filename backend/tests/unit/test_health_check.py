"""
Unit tests for health check endpoints.
"""

from unittest.mock import MagicMock, patch

from app.api.v1.endpoints.health import (
    check_postgres,
    check_redis,
    check_worker_queue,
    health_check,
    system_status,
)
from app.schemas.health import StatusResponse
from sqlalchemy.orm import Session


class TestPostgresCheck:
    """Tests for PostgreSQL connectivity check."""

    def test_check_postgres_success(self):
        """Test successful PostgreSQL connection check."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value = MagicMock()

        result = check_postgres(mock_db)

        assert result == "connected"
        mock_db.execute.assert_called_once()

    def test_check_postgres_failure(self):
        """Test failed PostgreSQL connection check."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.side_effect = Exception("Connection failed")

        result = check_postgres(mock_db)

        assert result == "disconnected"
        mock_db.execute.assert_called_once()

    def test_check_postgres_handles_timeout(self):
        """Test PostgreSQL check handles timeout."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.side_effect = TimeoutError("Query timeout")

        result = check_postgres(mock_db)

        assert result == "disconnected"


class TestRedisCheck:
    """Tests for Redis connectivity check."""

    @patch("app.api.v1.endpoints.health.get_redis_client")
    @patch("app.api.v1.endpoints.health.check_redis_health", return_value=True)
    def test_check_redis_success(self, mock_health, mock_get_redis_client):
        """Test successful Redis connection check."""
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis

        result = check_redis()

        assert result == "connected"
        mock_health.assert_called_once()
        mock_redis.close.assert_called_once()

    @patch("app.api.v1.endpoints.health.get_redis_client")
    @patch("app.api.v1.endpoints.health.check_redis_health", return_value=False)
    def test_check_redis_failure(self, mock_health, mock_get_redis_client):
        """Test failed Redis connection check."""
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis

        result = check_redis()

        assert result == "disconnected"
        mock_redis.close.assert_called_once()

    def test_check_redis_returns_unknown_if_not_configured(self):
        """Test Redis check returns 'unknown' if client not configured."""
        with patch("app.api.v1.endpoints.health.get_redis_client", return_value=None):
            result = check_redis()
            assert result == "unknown"


class TestWorkerQueueCheck:
    """Tests for RQ worker queue check."""

    @patch("app.api.v1.endpoints.health.get_redis_client")
    def test_check_worker_queue_no_workers_returns_inactive(self, mock_get_redis):
        """Test worker queue returns 'inactive' when Redis is up but no workers are registered."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_get_redis.return_value = mock_redis

        # Patch rq.Worker directly since it is imported inside the function
        with patch("rq.Worker") as mock_worker_cls:
            mock_worker_cls.all.return_value = []
            result = check_worker_queue()

        assert result == "inactive"
        mock_redis.close.assert_called_once()

    @patch("app.api.v1.endpoints.health.get_redis_client")
    def test_check_worker_queue_with_workers_returns_active(self, mock_get_redis):
        """Test worker queue returns 'active' when at least one worker is registered."""
        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        with patch("rq.Worker") as mock_worker_cls:
            mock_worker_cls.all.return_value = [MagicMock()]
            result = check_worker_queue()

        assert result == "active"

    def test_check_worker_queue_redis_unavailable(self):
        """Test worker queue check when Redis unavailable."""
        # When get_redis_client returns None
        with patch("app.api.v1.endpoints.health.get_redis_client", return_value=None):
            result = check_worker_queue()
            assert result == "unknown"


class TestHealthCheckEndpoint:
    """Tests for the simple liveness probe (GET /api/health)."""

    def test_health_check_returns_ok(self):
        """Test that the simple health check returns {"status": "ok"}."""
        result = health_check()
        assert result == {"status": "ok"}

    def test_health_check_always_200(self):
        """Health check has no dependencies and always succeeds."""
        # Call multiple times to confirm idempotency
        for _ in range(3):
            result = health_check()
            assert result["status"] == "ok"


class TestSystemStatusEndpoint:
    """Tests for the system readiness probe (GET /api/status)."""

    def test_system_status_all_connected(self):
        """Test system status when all components are healthy."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis,
            patch("app.api.v1.endpoints.health.check_redis_health", return_value=True),
        ):
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            result = system_status(response=mock_response, db=mock_db)

        assert isinstance(result, StatusResponse)
        assert result.api == "ready"
        assert result.db == "connected"
        assert result.redis == "connected"
        # status_code must NOT have been set to 503
        assert mock_response.status_code != 503

    def test_system_status_postgres_down_returns_503(self):
        """Test system status sets 503 when PostgreSQL is down."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.side_effect = Exception("Connection failed")
        mock_response = MagicMock()

        with (
            patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis,
            patch("app.api.v1.endpoints.health.check_redis_health", return_value=True),
        ):
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            result = system_status(response=mock_response, db=mock_db)

        assert result.api == "ready"
        assert result.db == "disconnected"
        assert mock_response.status_code == 503

    def test_system_status_redis_down_returns_503(self):
        """Test system status sets 503 when Redis is down."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value = MagicMock()
        mock_response = MagicMock()

        with (
            patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis,
            patch("app.api.v1.endpoints.health.check_redis_health", return_value=False),
        ):
            mock_redis = MagicMock()
            mock_get_redis.return_value = mock_redis

            result = system_status(response=mock_response, db=mock_db)

        assert result.api == "ready"
        assert result.db == "connected"
        assert result.redis == "disconnected"
        assert mock_response.status_code == 503

    def test_system_status_redis_unknown_does_not_503(self):
        """Test system status does not set 503 when Redis is unconfigured (unknown)."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value = MagicMock()
        mock_response = MagicMock()

        with patch("app.api.v1.endpoints.health.get_redis_client", return_value=None):
            result = system_status(response=mock_response, db=mock_db)

        assert result.api == "ready"
        assert result.db == "connected"
        assert result.redis == "unknown"
        assert mock_response.status_code != 503

    def test_system_status_both_down_returns_503(self):
        """Test system status sets 503 when both DB and Redis are down."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.side_effect = Exception("DB unreachable")
        mock_response = MagicMock()

        with (
            patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis,
            patch("app.api.v1.endpoints.health.check_redis_health", return_value=False),
        ):
            mock_get_redis.return_value = MagicMock()

            result = system_status(response=mock_response, db=mock_db)

        assert result.api == "ready"
        assert result.db == "disconnected"
        assert result.redis == "disconnected"
        assert mock_response.status_code == 503

    def test_system_status_response_model(self):
        """Test that response conforms to StatusResponse schema."""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.return_value = MagicMock()
        mock_response = MagicMock()

        with (
            patch("app.api.v1.endpoints.health.get_redis_client") as mock_get_redis,
            patch("app.api.v1.endpoints.health.check_redis_health", return_value=True),
        ):
            mock_get_redis.return_value = MagicMock()

            result = system_status(response=mock_response, db=mock_db)

        assert isinstance(result, StatusResponse)
        assert result.api in ["ready"]
        assert result.db in ["connected", "disconnected", "unknown"]
        assert result.redis in ["connected", "disconnected", "unknown"]
