#!/bin/sh
# Rewrite LORAD_CONFIG string literals. Used at image build.
# Production (LORAD_ENV=production): domain defaults to radio.local.
set -e

CONFIG="${1:-js/config.js}"

if [ ! -f "$CONFIG" ]; then
  echo "apply-config.sh: missing $CONFIG" >&2
  exit 1
fi

ENV="${LORAD_ENV:-development}"

if [ "$ENV" = "production" ]; then
  DOMAIN="${LORAD_DOMAIN:-radio.local}"
  SCHEME="${LORAD_SCHEME:-http}"
  API_PATH="${LORAD_API_PATH:-/radio/api}"
  RADIO_PATH="${LORAD_RADIO_PATH:-/radio}"
  WS_PATH="${LORAD_WS_PATH:-/radio/ws}"
else
  DOMAIN="${LORAD_DOMAIN:-}"
  SCHEME="${LORAD_SCHEME:-}"
  API_PATH="${LORAD_API_PATH:-}"
  RADIO_PATH="${LORAD_RADIO_PATH:-}"
  WS_PATH="${LORAD_WS_PATH:-}"
fi

API_URL="${LORAD_API_URL:-}"
RADIO_URL="${LORAD_RADIO_URL:-}"
WS_URL="${LORAD_WS_URL:-}"

set_const() {
  key="$1"
  val="$2"
  [ -n "$val" ] || return 0
  escaped=$(printf '%s' "$val" | sed 's/[\\/&]/\\&/g')
  sed -i "s/const ${key} = \"[^\"]*\"/const ${key} = \"${escaped}\"/" "$CONFIG"
}

set_const domain "$DOMAIN"
set_const scheme "$SCHEME"
set_const apiPath "$API_PATH"
set_const radioPath "$RADIO_PATH"
set_const wsPath "$WS_PATH"
set_const apiUrlOverride "$API_URL"
set_const radioUrlOverride "$RADIO_URL"
set_const wsUrlOverride "$WS_URL"
