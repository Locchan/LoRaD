#!/bin/sh

set -e
set -x

apk add ffmpeg
pip install --no-cache-dir poetry
(cd purest && poetry build && pip install --no-cache-dir dist/*.whl)
poetry build
pip install --no-cache-dir dist/*.whl
cp /tmp/lorad/lorad_main.py /usr/bin/lorad
chmod +x /usr/bin/lorad
ln -s /usr/share/zoneinfo/Europe/Minsk /etc/localtime
echo "${VERSION}" > /version
pip freeze > /packages
sed -i '/lorad/d' /packages
sed -i '/purest/d' /packages
rm -rf /tmp/lorad
