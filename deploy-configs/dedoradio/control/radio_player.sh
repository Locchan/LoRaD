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
# Fill more than the 1KB probe before taking the sound card from gimn.
PREBUFFER_BYTES=32768

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

wait_gimn_inactive() {
  local i
  for i in $(seq 1 40); do
    if ! systemctl is-active --quiet gimn.service; then
      sleep 0.25
      return 0
    fi
    sleep 0.05
  done
  sleep 0.25
}

play_buffered_stream() {
  local buf curl_pid tail_pid size i
  buf=$(mktemp -p /dev/shm lorad-radio.XXXXXX 2>/dev/null || mktemp)
  $RT_FETCH curl --fail --silent --show-error --speed-limit 1024 --speed-time 10 "$URL" -o "$buf" &
  curl_pid=$!
  size=0
  for i in $(seq 1 100); do
    if ! kill -0 "$curl_pid" 2>/dev/null; then
      break
    fi
    size=$(stat -c%s "$buf" 2>/dev/null || echo 0)
    if [ "$size" -gt "$PREBUFFER_BYTES" ]; then
      break
    fi
    sleep 0.1
  done
  if [ "${size:-0}" -le 1024 ]; then
    echo "Stream prebuffer failed (got ${size:-0} bytes)."
    kill "$curl_pid" 2>/dev/null
    wait "$curl_pid" 2>/dev/null
    rm -f "$buf"
    return 1
  fi
  systemctl stop gimn
  wait_gimn_inactive
  echo "Stream is available, starting playback..."
  (
    tail -c +1 -f "$buf" &
    tail_pid=$!
    wait "$curl_pid"
    sleep 0.2
    kill "$tail_pid" 2>/dev/null
    wait "$tail_pid" 2>/dev/null
  ) | $RT_PLAYER mpg123 -q -b "$PLAYER_BUFFER_KB" -
  kill "$curl_pid" 2>/dev/null
  wait "$curl_pid" 2>/dev/null
  rm -f "$buf"
  echo "mpg123 exited or stream ended."
}


while true; do
  echo "Checking stream availability..."
  if check_stream; then
    play_buffered_stream
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
