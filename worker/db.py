"""Worker database session management."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_SessionLocal: sessionmaker | None = None
_Engine: Engine | None = None


def _get_session_factory() -> sessionmaker:
    global _Engine, _SessionLocal
    if _SessionLocal is None:
        from worker.config import get_settings

        settings = get_settings()
        _Engine = create_engine(settings.database_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_Engine)
    return _SessionLocal


def dispose_worker_db_engine() -> None:
    """Close the parent engine before RQ forks job processes.

    RQ forks child processes after worker startup. Reset the factory so each
    child creates its own engine and PostgreSQL connection pool.
    """
    global _Engine, _SessionLocal
    if _Engine is not None:
        _Engine.dispose()
    _Engine = None
    _SessionLocal = None


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, committing on success and rolling back on error."""
    factory = _get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def commit_transaction(session: Session) -> None:
    """Commit a transaction at an explicit worker persistence boundary."""
    session.commit()
