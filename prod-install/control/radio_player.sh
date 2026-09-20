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
# The unit's realtime policy is not inherited by the pipeline, so ask for it per process.
# mpg123 owns the sound card deadline, curl only has to keep the pipe fed.
RT_PLAYER="chrt -f 20 ionice -c1"
RT_FETCH="chrt -f 15"
# ~6 seconds of decoded audio, so a CPU spike cannot reach the speaker.
PLAYER_BUFFER_KB=1024

if ! command -v chrt >/dev/null || ! chrt -f 20 true 2>/dev/null; then
  echo "radio_player: no realtime scheduling available, running normally" >&2
  RT_PLAYER=""
  RT_FETCH=""
fi

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
    $RT_FETCH curl --fail --silent --show-error --speed-limit 1024 --speed-time 10 "$URL" \
      | $RT_PLAYER mpg123 -q -b "$PLAYER_BUFFER_KB" -
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
