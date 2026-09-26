#!/bin/sh
# Build and (re)start the frontend image for local testing.
# Browser talks to the host API/stream/WS: 127.0.0.1:5476, 5475, 5478.
set -e

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
NAME="${LORAD_FRONT_NAME:-lorad-front-local}"
IMAGE="${LORAD_FRONT_IMAGE:-lorad-front-local}"
PORT="${LORAD_FRONT_PORT:-5477}"
API_URL="${LORAD_API_URL:-http://127.0.0.1:5476}"
RADIO_URL="${LORAD_RADIO_URL:-http://127.0.0.1:5475}"
WS_URL="${LORAD_WS_URL:-ws://127.0.0.1:5478}"

docker buildx build --load \
  --build-arg LORAD_API_URL="$API_URL" \
  --build-arg LORAD_RADIO_URL="$RADIO_URL" \
  --build-arg LORAD_WS_URL="$WS_URL" \
  -t "$IMAGE" \
  "$ROOT"

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" -p "${PORT}:5477" "$IMAGE" >/dev/null

echo "UI:     http://127.0.0.1:${PORT}/ui/"
echo "API:    ${API_URL}"
echo "WS:     ${WS_URL}"
echo "Stream: ${RADIO_URL}"
