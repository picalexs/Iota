"""
FastAPI application entry point.

Sets up the API with CORS middleware and core endpoints.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.logging import setup_logging
from app.exceptions import APIException
from app.exceptions.handlers import (
    api_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.middleware import RequestLoggingMiddleware

logger = logging.getLogger(__name__)


async def _background_pubchem_sync(app: FastAPI) -> None:
    """Background task: sync curated molecules from PubChem after API startup."""
    from app.services.pubchem_sync import sync_from_pubchem

    logger.info("Starting background PubChem molecule sync...")
    session_factory = app.state.session_factory
    db = session_factory()
    try:
        result = await sync_from_pubchem(db)
        logger.info(
            "PubChem sync complete: added=%d, skipped=%d, failed=%d",
            result.added,
            result.skipped,
            len(result.failed),
        )
    except Exception:
        logger.exception("Background PubChem sync encountered an error")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup/shutdown events."""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.log_level}")

    from app.database.session import (
        create_async_engine_sync,
        create_async_session_factory,
        create_engine_sync,
        create_session_factory_sync,
    )

    app.state.engine = create_engine_sync(
        settings.sqlalchemy_database_uri,
        echo=settings.database_echo,
    )
    app.state.session_factory = create_session_factory_sync(app.state.engine)

    app.state.async_engine = create_async_engine_sync(
        settings.sqlalchemy_database_uri_async,
        echo=settings.database_echo,
    )
    app.state.async_session_factory = create_async_session_factory(app.state.async_engine)

    logger.info("Database engines and session factories initialized")

    if not settings.skip_pubchem_sync:
        app.state.pubchem_sync_task = asyncio.create_task(_background_pubchem_sync(app))

    yield

    logger.info("Shutting down application")

    # Dispose of engines.
    engine = getattr(app.state, "engine", None)
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            logger.exception("Failed to dispose synchronous engine")

    async_engine = getattr(app.state, "async_engine", None)
    if async_engine is not None:
        try:
            await async_engine.dispose()
        except Exception:
            logger.exception("Failed to dispose async engine")

    logger.info("Database engines disposed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    try:
        settings = get_settings()
    except Exception as exc:
        setup_logging(log_level="INFO")
        logger.exception("Failed to load settings: %s", exc)
        raise SystemExit(
            "Backend configuration failed; check required environment variables"
        ) from exc

    setup_logging(log_level=settings.log_level)

    docs_enabled = bool(settings.docs_enabled)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_exception_handler(APIException, api_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore

    # FastAPI middleware is wrapped in reverse registration order; request
    # logging stays outermost while CORS remains the inner protocol middleware.
    app.add_middleware(  # NOSONAR
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint providing API information."""
        return JSONResponse(
            status_code=200,
            content={
                "message": "Quantum VQE Studio API",
                "version": settings.app_version,
                "docs": "/docs" if docs_enabled else None,
            },
        )

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
