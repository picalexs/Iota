#!/bin/sh

set -eu

LOCKFILE=package-lock.json
STAMP=node_modules/.package-lock.sha256

current_lock_hash() {
  sha256sum "$LOCKFILE" | awk '{print $1}'
}

needs_install() {
  [ ! -d node_modules ] && return 0
  [ ! -f "$STAMP" ] && return 0

  [ "$(cat "$STAMP")" != "$(current_lock_hash)" ]
}

if [ ! -f "$LOCKFILE" ]; then
  echo "Missing $LOCKFILE; cannot install frontend dependencies." >&2
  exit 1
fi

if needs_install; then
  echo "Installing frontend dependencies to match $LOCKFILE..."
  npm ci --legacy-peer-deps
  current_lock_hash > "$STAMP"
fi

exec npm run dev
