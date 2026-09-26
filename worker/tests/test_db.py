"""Tests for worker database engine lifecycle."""

from unittest.mock import MagicMock, patch

from worker import db as db_module


def test_dispose_worker_db_engine_resets_factory(monkeypatch):
    """Reset the engine and session factory before RQ forks children."""
    engine = MagicMock()
    factory = MagicMock()

    monkeypatch.setattr(db_module, "_Engine", engine)
    monkeypatch.setattr(db_module, "_SessionLocal", factory)

    db_module.dispose_worker_db_engine()

    engine.dispose.assert_called_once_with()
    assert db_module._Engine is None
    assert db_module._SessionLocal is None


def test_session_factory_stores_engine(monkeypatch):
    """Keep the engine reference so startup can dispose it before forking."""
    engine = MagicMock()
    settings = MagicMock(database_url="postgresql://example/database")

    monkeypatch.setattr(db_module, "_Engine", None)
    monkeypatch.setattr(db_module, "_SessionLocal", None)
    with patch("worker.config.get_settings", return_value=settings):
        with patch("worker.db.create_engine", return_value=engine):
            db_module._get_session_factory()

    assert db_module._Engine is engine
    assert db_module._SessionLocal is not None
