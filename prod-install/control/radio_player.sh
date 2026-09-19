#!/bin/bash

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$( cd -P "$( dirname "$SOURCE" )" && pwd )"

URL="127.0.0.1:5475"
RETRY_DELAY=5
TIMEOUT=10

check_stream() {
  headers=$(curl --silent --fail --max-time "$TIMEOUT" --range 0-1023 -D - "$URL" -o /dev/null)
  content_type=$(echo "$headers" | grep -i '^Content-Type:' | tr -d '\r' | awk '{print $2}')
  [ "$content_type" = "audio/mpeg" ]
}


while true; do
  echo "Checking stream availability..."
  if check_stream; then
    systemctl stop gimn
    echo "Stream is available, starting playback..."
    curl --fail --silent --show-error --speed-limit 1024 --speed-time 10 "$URL" | mpg123 -q -
    echo "mpg123 exited or stream ended."
    if ! systemctl is-active --quiet gimn.service; then
      systemctl start gimn
    fi
  else
    if ! systemctl is-active --quiet gimn.service; then
      systemctl start gimn
    fi
    echo "Stream not available, will retry in $RETRY_DELAY seconds."
  fi
  sleep $RETRY_DELAY
done
