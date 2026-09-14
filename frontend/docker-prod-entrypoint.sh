#!/bin/sh

set -eu

TOKEN_FILE="${LOCAL_OPERATOR_TOKEN_FILE:-/app/local-operator/operator-access.token}"

generate_token() {
  if [ -n "${LOCAL_OPERATOR_TOKEN:-}" ]; then
    printf '%s' "$LOCAL_OPERATOR_TOKEN"
    return
  fi

  if [ ! -f "$TOKEN_FILE" ]; then
    mkdir -p "$(dirname "$TOKEN_FILE")"
    umask 077
    head -c 32 /dev/urandom | base64 | tr -d '\n' | tr '+/' '-_' >"$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
  fi

  tr -d '\n' <"$TOKEN_FILE"
}

export API_TARGET_URL="${API_TARGET_URL:-http://api:8000}"
export LOCAL_OPERATOR_TOKEN_RESOLVED="$(generate_token)"
export NGINX_SERVER_NAME="${NGINX_SERVER_NAME:-_}"
