#!/bin/bash
# Install the radio.local host stack onto this machine:
#   /opt/radio  +  systemd (radio, gimn, volume)  +  nginx  +  /usr/bin links
#
# Usage (as root):
#   ./install.sh
#   ./install.sh --no-packages
#   ./install.sh --no-nginx
#   ./install.sh --no-gpio
#
# Does not start Docker and does not overwrite an existing config.json / .env.
# After this: fill /opt/radio/lorad/data/config.json, load images, then:
#   cd /opt/radio/lorad && docker compose up -d
#   systemctl start radio volume

set -euo pipefail

DEST=/opt/radio
INSTALL_PACKAGES=1
INSTALL_NGINX=1
INSTALL_GPIO=1

SRC=$(cd "$(dirname "$0")" && pwd)

while [ $# -gt 0 ]; do
  case "$1" in
    --no-packages) INSTALL_PACKAGES=0 ;;
    --no-nginx) INSTALL_NGINX=0 ;;
    --no-gpio) INSTALL_GPIO=0 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
  shift
done

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root." >&2
  exit 1
fi

if [ "$INSTALL_PACKAGES" -eq 1 ]; then
  echo "Installing packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    curl \
    mpg123 \
    alsa-utils \
    nginx \
    python3 \
    python3-libgpiod \
    docker.io \
    docker-compose-plugin
fi

echo "Installing tree to ${DEST}..."
mkdir -p "${DEST}/control" "${DEST}/lorad/data" "${DEST}/lorad_build"
cp "${SRC}/README.md" /opt/README.md

cp -a "${SRC}/control/." "${DEST}/control/"
chmod 755 \
  "${DEST}/control/radio_player.sh" \
  "${DEST}/control/gimn.sh" \
  "${DEST}/control/volume.sh" \
  "${DEST}/control/volume_knob.py"

cp -a "${SRC}/lorad/docker-compose.yml" "${DEST}/lorad/docker-compose.yml"
cp -a "${SRC}/lorad_build/build-upgrade.sh" "${DEST}/lorad_build/build-upgrade.sh"
chmod 755 "${DEST}/lorad_build/build-upgrade.sh"

if [ ! -f "${DEST}/lorad/.env" ]; then
  cp "${SRC}/lorad/env.example" "${DEST}/lorad/.env"
  echo "Wrote ${DEST}/lorad/.env from env.example — set LORAD_VERSION to your image tag."
else
  echo "Keeping existing ${DEST}/lorad/.env"
fi

ln -sfn "${DEST}/lorad/.env" "${DEST}/lorad_build/config"

if [ ! -f "${DEST}/lorad/data/stations.json" ]; then
  cp "${SRC}/lorad/data/stations.json" "${DEST}/lorad/data/stations.json"
fi

if [ ! -f "${DEST}/lorad/data/config.json" ]; then
  cp "${SRC}/lorad/data/config.example.json" "${DEST}/lorad/data/config.json"
  echo "Wrote ${DEST}/lorad/data/config.json from example — fill secrets before starting lorad."
else
  echo "Keeping existing ${DEST}/lorad/data/config.json"
fi

mkdir -p \
  "${DEST}/lorad/data/resources/fallback_tracks" \
  "${DEST}/lorad/data/resources/ads" \
  "${DEST}/lorad/data/resources/random_voices" \
  "${DEST}/lorad/data/neurovoice/digests"

if [ -d "${SRC}/lorad/data/resources" ]; then
  cp -an "${SRC}/lorad/data/resources/." "${DEST}/lorad/data/resources/" 2>/dev/null || true
fi

echo "Linking /usr/bin helpers..."
ln -sfn "${DEST}/control/radio_player.sh" /usr/bin/radio_player
ln -sfn "${DEST}/control/gimn.sh" /usr/bin/gimn
ln -sfn "${DEST}/control/volume.sh" /usr/bin/volume

echo "Installing systemd units (symlinks into ${DEST}/control/systemd)..."
for unit in radio.service gimn.service; do
  ln -sfn "${DEST}/control/systemd/${unit}" "/etc/systemd/system/${unit}"
done
if [ "$INSTALL_GPIO" -eq 1 ]; then
  ln -sfn "${DEST}/control/systemd/volume.service" /etc/systemd/system/volume.service
fi

systemctl daemon-reload
systemctl enable radio.service gimn.service
if [ "$INSTALL_GPIO" -eq 1 ]; then
  systemctl enable volume.service
fi

if [ "$INSTALL_NGINX" -eq 1 ]; then
  echo "Installing nginx site..."
  mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
  cp "${SRC}/nginx/lorad.conf" /etc/nginx/sites-available/lorad
  ln -sfn /etc/nginx/sites-available/lorad /etc/nginx/sites-enabled/lorad
  if [ -L /etc/nginx/sites-enabled/default ] || [ -f /etc/nginx/sites-enabled/default ]; then
    rm -f /etc/nginx/sites-enabled/default
  fi
  nginx -t
  systemctl enable nginx
  systemctl reload nginx || systemctl start nginx
fi

echo
echo "Installed. Next:"
echo "  1. Put gimn.mp3 (and news_jingle.mp3) in ${DEST}/lorad/data/resources/fallback_tracks and .../resources/"
echo "  2. Edit ${DEST}/lorad/data/config.json and ${DEST}/lorad/.env"
echo "  3. Load or build images local/lorad-arm and local/lorad-front-arm for LORAD_VERSION"
echo "  4. cd ${DEST}/lorad && docker compose up -d"
echo "  5. systemctl start radio"
if [ "$INSTALL_GPIO" -eq 1 ]; then
  echo "  6. systemctl start volume"
fi
