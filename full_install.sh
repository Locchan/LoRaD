#!/bin/sh

set -e
set -x

apk add ffmpeg
pip install --no-cache-dir poetry
poetry build
pip install --no-cache-dir dist/*.whl
cp /tmp/lorad/lorad_main.py /usr/bin/lorad
chmod +x /usr/bin/lorad
cp -r /tmp/lorad/frontend/dist/lorad-frontend/browser/* /app/ui/
rm -rf /tmp/lorad
ln -s /usr/share/zoneinfo/Europe/Minsk /etc/localtime
echo "${VERSION}" > /version
pip freeze > /packages