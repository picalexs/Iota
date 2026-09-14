"""
Tests for seed_molecules function in init_db.py.

Validates that seed_molecules correctly:
1. Calls sync_from_pubchem with the database session
2. Handles idempotent behavior (molecules already present are skipped)
3. Logs warnings for failed molecules
4. Uses asyncio.run to execute the async sync function
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from app.services.pubchem_sync import SyncResult

TEST_DB_URL = "postgresql://localhost/test"
CREATE_ENGINE_PATCH = "init_db.create_engine"
SYNC_FROM_PUBCHEM_PATCH = "init_db.sync_from_pubchem"
SESSION_PATCH = "sqlalchemy.orm.Session"
LOGGER_PATCH = "init_db.logger"


class TestSeedMolecules:
    """Tests for the seed_molecules function."""

    @pytest.fixture
    def mock_session(self) -> Mock:
        """Provide a mock SQLAlchemy session."""
        return MagicMock()

    @pytest.fixture
    def mock_sync_result(self) -> SyncResult:
        """Provide a mock SyncResult."""
        return SyncResult(added=10, skipped=46, failed=[])

    def test_seed_molecules_calls_sync_from_pubchem(
        self,
        mock_session: Mock,
        mock_sync_result: SyncResult,
    ) -> None:
        """Test that seed_molecules correctly calls sync_from_pubchem."""
        db_url = TEST_DB_URL

        # Mock create_engine and Session
        with patch(CREATE_ENGINE_PATCH) as mock_engine_factory:
            mock_engine = MagicMock()
            mock_engine_factory.return_value = mock_engine
            mock_engine.__enter__ = MagicMock(return_value=mock_engine)
            mock_engine.__exit__ = MagicMock(return_value=False)

            # Mock sync_from_pubchem async function
            mock_sync = AsyncMock(return_value=mock_sync_result)
            with patch(SYNC_FROM_PUBCHEM_PATCH, mock_sync):
                # Mock sqlalchemy.orm.Session
                with patch(SESSION_PATCH) as mock_session_factory:
                    mock_session_factory.return_value.__enter__.return_value = mock_session

                    # Import and call seed_molecules
                    import init_db

                    init_db.seed_molecules(db_url)

                    # Verify sync_from_pubchem was called with the session
                    mock_sync.assert_called_once()

    def test_seed_is_idempotent_skips_existing(self) -> None:
        """Test that seed_molecules skips molecules already in database."""
        db_url = TEST_DB_URL

        # Return a SyncResult with all molecules skipped
        mock_result = SyncResult(added=0, skipped=56, failed=[])

        with patch(CREATE_ENGINE_PATCH) as mock_engine_factory:
            mock_engine = MagicMock()
            mock_engine_factory.return_value = mock_engine

            mock_sync = AsyncMock(return_value=mock_result)
            with patch(SYNC_FROM_PUBCHEM_PATCH, mock_sync):
                with patch(SESSION_PATCH) as mock_session_factory:
                    mock_session_factory.return_value.__enter__.return_value = MagicMock()
                    with patch(LOGGER_PATCH) as mock_logger:
                        import init_db

                        init_db.seed_molecules(db_url)

                        # Verify that logger was called with skipped info
                        assert mock_logger.info.called

    def test_seed_molecules_skips_network_sync_when_database_is_not_empty(self) -> None:
        """Existing databases skip the expensive PubChem seed pass on startup."""
        db_url = TEST_DB_URL

        with patch(CREATE_ENGINE_PATCH) as mock_engine_factory:
            mock_engine = MagicMock()
            mock_engine_factory.return_value = mock_engine

            mock_sync = AsyncMock()
            with patch(SYNC_FROM_PUBCHEM_PATCH, mock_sync):
                with patch(SESSION_PATCH) as mock_session_factory:
                    mock_session = MagicMock()
                    mock_session.execute.return_value.scalar.return_value = 5
                    mock_session_factory.return_value.__enter__.return_value = mock_session
                    with patch(LOGGER_PATCH) as mock_logger:
                        import init_db

                        init_db.seed_molecules(db_url)

                        mock_sync.assert_not_called()
                        mock_logger.info.assert_called_with(
                            "Molecule seeding skipped because the database already contains %d molecules.",
                            5,
                        )

    def test_seed_logs_failures(self) -> None:
        """Test that seed_molecules logs warnings for failed molecules."""
        db_url = TEST_DB_URL

        # Return a SyncResult with some failures
        mock_result = SyncResult(
            added=54,
            skipped=0,
            failed=["dihydrogen", "water"],  # Two failed molecules
        )

        with patch(CREATE_ENGINE_PATCH) as mock_engine_factory:
            mock_engine = MagicMock()
            mock_engine_factory.return_value = mock_engine

            mock_sync = AsyncMock(return_value=mock_result)
            with patch(SYNC_FROM_PUBCHEM_PATCH, mock_sync):
                with patch(SESSION_PATCH) as mock_session_factory:
                    mock_session_factory.return_value.__enter__.return_value = MagicMock()
                    with patch(LOGGER_PATCH) as mock_logger:
                        import init_db

                        init_db.seed_molecules(db_url)

                        # Verify that logger.warning was called with failed molecules
                        assert mock_logger.warning.called

    def test_seed_molecules_uses_asyncio_run(self) -> None:
        """Test that seed_molecules uses asyncio.run to execute async function."""
        db_url = TEST_DB_URL

        mock_result = SyncResult(added=10, skipped=46, failed=[])

        with patch(CREATE_ENGINE_PATCH) as mock_engine_factory:
            mock_engine = MagicMock()
            mock_engine_factory.return_value = mock_engine

            mock_sync = Mock(return_value=object())
            with patch(SYNC_FROM_PUBCHEM_PATCH, mock_sync):
                with patch(SESSION_PATCH) as mock_session_factory:
                    mock_session_factory.return_value.__enter__.return_value = MagicMock()
                    with patch("init_db.asyncio.run") as mock_asyncio_run:
                        mock_asyncio_run.return_value = mock_result
                        with patch(LOGGER_PATCH):
                            import init_db

                            init_db.seed_molecules(db_url)

                            # Verify asyncio.run was called
                            assert mock_asyncio_run.called
