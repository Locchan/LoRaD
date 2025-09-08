#!/bin/sh

set -e
set -x

apk add ffmpeg
pip install poetry
poetry build
pip install --upgrade --no-deps --force-reinstall dist/*.whl
pip install --upgrade dist/*.whl
cp /tmp/lorad/lorad_main.py /usr/bin/lorad
chmod +x /usr/bin/lorad
ln -sf /usr/share/zoneinfo/Europe/Minsk /etc/localtime
echo "${VERSION}" > /version
pip freeze > /packages
rm -rf /tmp/lorad