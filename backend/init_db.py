#!/usr/bin/env python3
"""
Initialize the database before API startup.

Runs Alembic migrations to ``head`` and optionally seeds example molecules.

Usage::

    python init_db.py [--skip-seed]

Environment variables (inherited from the container):

    DATABASE_URL   - Required. PostgreSQL connection URL.
    SKIP_SEED      - Set to ``true`` to bypass molecule seeding (overrides flag).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from alembic import command as alembic_command  # type: ignore[attr-defined]
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("init_db")
logging.getLogger("httpx").setLevel(logging.WARNING)

# Configure logging before app imports so first messages are captured.
from app.config import get_settings  # noqa: E402
from app.services.pubchem_sync import sync_from_pubchem  # noqa: E402

_MAX_RETRIES: int = 15
_INITIAL_WAIT: float = 1.0  # seconds
_BACKOFF_FACTOR: float = 1.5
_MAX_WAIT: float = 20.0  # seconds


def _redact_url(url: str) -> str:
    """Return *url* with the password component replaced by ``***``."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            safe_netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return urlunparse(parsed._replace(netloc=safe_netloc))
    except Exception:  # pragma: no cover
        pass
    return url


def wait_for_database(db_url: str) -> None:
    """
    Probe the database with ``SELECT 1`` using exponential backoff.

    Raises ``OperationalError`` after *_MAX_RETRIES* failed attempts so the
    container exits with a non-zero code and Docker can restart it.
    """
    engine = create_engine(db_url, pool_pre_ping=True)
    wait = _INITIAL_WAIT

    try:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                logger.info("Postgres is ready.")
                return
            except OperationalError:
                if attempt == _MAX_RETRIES:
                    logger.exception(
                        "Cannot connect to Postgres after %d attempts.",
                        _MAX_RETRIES,
                    )
                    raise
                logger.warning(
                    "Postgres not ready yet (attempt %d/%d) — retrying in %.1fs…",
                    attempt,
                    _MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
                wait = min(wait * _BACKOFF_FACTOR, _MAX_WAIT)
    finally:
        engine.dispose()


def _is_db_at_head(alembic_cfg: AlembicConfig, db_url: str) -> bool:
    """
    Check if the database is already at the current migration head.

    Uses a simpler approach: reads the latest migration ID from the script directory
    and compares it with the current DB revision from the alembic_version table.
    Returns True if they match, False otherwise or if any error occurs.
    """
    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            heads = script_dir.get_heads()
            if not heads:
                return False

            target_head = heads[0]

            try:
                result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                row = result.fetchone()
                current_version = row[0] if row else None
            except Exception:
                return False

            is_at_head = current_version == target_head
            return is_at_head
    except Exception:
        logger.exception("Error checking migration status. Migrations will run.")
        return False
    finally:
        engine.dispose()


def run_migrations() -> None:
    """
    Run ``alembic upgrade head`` programmatically.

    The ``sqlalchemy.url`` in *alembic.ini* is a placeholder; we override it
    at runtime from the app settings so the environment variable is always
    the authoritative source.
    """
    ini_path = Path(__file__).parent / "alembic.ini"
    if not ini_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {ini_path}")

    alembic_cfg = AlembicConfig(str(ini_path))

    settings = get_settings()
    alembic_cfg.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)

    if _is_db_at_head(alembic_cfg, settings.sqlalchemy_database_uri):
        logger.info("Database is already at the current migration head. Skipping upgrade.")
        return

    logger.info("Running Alembic migrations (upgrade head)…")
    alembic_command.upgrade(alembic_cfg, "head")
    logger.info("Migrations applied successfully.")


def seed_molecules(db_url: str) -> None:
    """
    Seed benchmark molecules from PubChem into the database.

    Fetches 3D geometry and full metadata for each curated molecule when the
    local database does not already contain molecules. Existing databases skip
    the network seed pass entirely so container restarts stay fast and quiet.
    """
    from sqlalchemy.orm import Session

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            molecule_count = session.execute(text("SELECT COUNT(*) FROM molecules")).scalar()
            if isinstance(molecule_count, int) and molecule_count > 0:
                logger.info(
                    "Molecule seeding skipped because the database already contains %d molecules.",
                    molecule_count,
                )
                return
            result = asyncio.run(sync_from_pubchem(session))
            logger.info(
                "PubChem seed complete: %d added, %d skipped, %d failed.",
                result.added,
                result.skipped,
                len(result.failed),
            )
            if result.failed:
                logger.warning("Failed to seed: %s", ", ".join(result.failed))
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize the QVS database: run migrations and optionally seed molecules.",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        default=False,
        help="Skip example molecule seeding (also honoured via SKIP_SEED=true env var).",
    )
    args = parser.parse_args()

    skip_seed: bool = args.skip_seed or os.getenv("SKIP_SEED", "false").lower() == "true"

    settings = get_settings()
    db_url = settings.sqlalchemy_database_uri

    logger.info("══════ Quantum VQE Studio — DB Init ══════")
    logger.info("Target: %s", _redact_url(db_url))

    wait_for_database(db_url)
    run_migrations()

    if skip_seed:
        logger.info("Molecule seeding skipped.")
    else:
        seed_molecules(db_url)

    logger.info("══════ DB Init complete ══════")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("DB Init failed")
        sys.exit(1)
