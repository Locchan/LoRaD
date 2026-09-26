#!/bin/bash
# Install the radio.locchan.dev host stack onto this machine:
#   /opt/services/lorad  +  nginx site "radio"  +  /opt/container_storage/lorad
#
# Usage (locchan has passwordless sudo; re-execs via sudo if needed):
#   ./install.sh
#   ./install.sh --no-packages
#   ./install.sh --no-nginx
#
# Does not overwrite an existing envfile.env / config.jsonc.
# Does not install media under resources/ — keep those on the host.
# After copying, always: nginx -t && nginx -s reload, then ${DEST}/restart.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  exec sudo -n "$0" "$@"
fi

DEST=/opt/services/lorad
DATA=/opt/container_storage/lorad
INSTALL_PACKAGES=1
INSTALL_NGINX=1

SRC=$(cd "$(dirname "$0")" && pwd)

while [ $# -gt 0 ]; do
  case "$1" in
    --no-packages) INSTALL_PACKAGES=0 ;;
    --no-nginx) INSTALL_NGINX=0 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

if [ "$INSTALL_PACKAGES" -eq 1 ]; then
  echo "Installing packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    curl \
    nginx \
    docker.io \
    docker-compose-plugin
fi

echo "Installing tree to ${DEST}..."
mkdir -p "${DEST}" "${DATA}"

cp "${SRC}/README.md" "${DEST}/README.md"

# Scripts + compose (overwrite scripts; preserve live env)
for f in \
  docker-compose.yaml \
  config \
  build \
  build-backend \
  build-frontend \
  build_upgrade-backend \
  rebuild \
  restart \
  start \
  start-frontend \
  status \
  stop \
  stop-frontend \
  upgrade-backend
do
  cp -a "${SRC}/lorad/${f}" "${DEST}/${f}"
done

chmod 755 \
  "${DEST}/build" \
  "${DEST}/build-backend" \
  "${DEST}/build-frontend" \
  "${DEST}/build_upgrade-backend" \
  "${DEST}/rebuild" \
  "${DEST}/restart" \
  "${DEST}/start" \
  "${DEST}/start-frontend" \
  "${DEST}/status" \
  "${DEST}/stop" \
  "${DEST}/stop-frontend" \
  "${DEST}/upgrade-backend"

if [ ! -f "${DEST}/envfile.env" ]; then
  cp "${SRC}/lorad/env.example" "${DEST}/envfile.env"
  echo "Wrote ${DEST}/envfile.env from env.example"
else
  echo "Keeping existing ${DEST}/envfile.env"
fi

if [ ! -f "${DATA}/stations.json" ]; then
  cp "${SRC}/lorad/data/stations.json" "${DATA}/stations.json"
fi

if [ ! -f "${DATA}/config.jsonc" ] && [ ! -f "${DATA}/config.json" ]; then
  cp "${SRC}/lorad/data/config.example.jsonc" "${DATA}/config.jsonc"
  echo "Wrote ${DATA}/config.jsonc from example — fill secrets before starting lorad."
else
  echo "Keeping existing config under ${DATA}"
fi

mkdir -p \
  "${DATA}/resources/fallback_tracks" \
  "${DATA}/resources/ads" \
  "${DATA}/resources/random_voices" \
  "${DATA}/neurovoice/digests"

if [ "$INSTALL_NGINX" -eq 1 ]; then
  echo "Installing nginx site..."
  mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
  cp "${SRC}/nginx/radio.conf" /etc/nginx/sites-available/radio
  ln -sfn /etc/nginx/sites-available/radio /etc/nginx/sites-enabled/radio
  systemctl enable nginx
  systemctl start nginx || true
fi

echo "Reloading nginx..."
nginx -t
nginx -s reload

echo "Restarting lorad at ${DEST}..."
(
  cd "${DEST}"
  ./restart
)

echo
echo "Deployed."
echo "  Config:  ${DATA}/config.jsonc (existing kept if present)"
echo "  Env:     ${DEST}/envfile.env (existing kept if present)"
echo "  Scripts: ${DEST}"
echo "  Nginx:   reloaded"
echo "  Stack:   restarted"
