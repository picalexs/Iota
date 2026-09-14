"""Database session management and engine factory helpers."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker


def create_engine_sync(database_url: str, echo: bool = False):
    """
    Create a synchronous SQLAlchemy engine.

    Used by lifespan to initialize the engine before storing in app.state.
    """
    return create_engine(
        database_url,
        pool_pre_ping=True,
        echo=echo,
    )


def create_session_factory_sync(engine):
    """
    Create a synchronous session factory.

    Used by lifespan to initialize the factory before storing in app.state.
    """
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )


def create_async_engine_sync(database_url: str, echo: bool = False):
    """
    Create an async SQLAlchemy engine.

    Used by lifespan to initialize the async engine before storing in app.state.
    """
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        echo=echo,
    )


def create_async_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """
    Create an async session factory.

    Used by lifespan to initialize the async factory before storing in app.state.
    """
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
