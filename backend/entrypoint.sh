#!/usr/bin/env sh
# 1. Runs database migrations and seeds example molecules via init_db.py.
# 2. Execs the command passed as arguments (defaults to the Dockerfile CMD).
#
# Environment variables forwarded to init_db.py:
#   DATABASE_URL  — required; set by docker-compose.
#   SKIP_SEED     — optional; set to "true" to bypass molecule seeding.
set -e

echo "=== QVS entrypoint: starting DB initialisation ==="
python /app/init_db.py
echo "=== QVS entrypoint: DB initialisation complete ==="

exec "$@"
