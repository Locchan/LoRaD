#!/bin/bash

set -e
set -x

source "config"

systemctl stop radio
docker stop lorad || :
docker stop lorad-front || :

rm -rf ./temp

git clone --branch ${LORAD_VERSION} https://github.com/locchan/lorad temp

cd ./temp/
VERSION_SHORT=$(/bin/sh getver.sh --short)
VERSION=$(/bin/sh getver.sh)
# Check if lorad backend upgrade image already exists
if ! docker image inspect local/lorad-arm:${LORAD_VERSION} >/dev/null 2>&1; then
  docker build \
    --build-arg "VERSION=$VERSION" \
    --build-arg TAG=${LORAD_VERSION} \
    -f Dockerfile_upgrade_arm \
    -t local/lorad-arm:${LORAD_VERSION} \
    .
else
  echo "Image local/lorad-arm:${LORAD_VERSION} already exists. Skipping build."
fi

cd frontend

# Check if frontend image already exists
if ! docker image inspect local/lorad-front-arm:${LORAD_VERSION} >/dev/null 2>&1; then
  docker build \
    -f Dockerfile \
    -t local/lorad-front-arm:${LORAD_VERSION} \
    .
else
  echo "Image local/lorad-front-arm:${LORAD_VERSION} already exists. Skipping build."
fi

cd ../..
rm -rf ./temp

systemctl start radio
