"""Export the FastAPI OpenAPI schema without starting application lifespan."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _configure_imports_and_defaults() -> None:
    """Make schema export independent from a local database or Redis service."""
    root = _repository_root()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "backend"))
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("LOCAL_OPERATOR_TOKEN", "openapi-generation-placeholder")
    os.environ.setdefault("SKIP_PUBCHEM_SYNC", "true")


def export_schema(output: Path) -> None:
    """Write a stable, formatted OpenAPI document to ``output``."""
    _configure_imports_and_defaults()

    from app.main import app

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_schema(args.output)


if __name__ == "__main__":
    main()
