#!/bin/bash

SRC="/opt/radio/lorad/data/resources/fallback_tracks/gimn.mp3"
PINNED="/dev/shm/lorad/pinned"
DEST="${PINNED}/gimn.mp3"

if [ ! -f "$SRC" ]; then
    echo "gimn: missing $SRC" >&2
    exit 1
fi

mkdir -p "$PINNED"
chmod 700 /dev/shm/lorad "$PINNED" 2>/dev/null || true
src_size=$(stat -c%s "$SRC")
if [ ! -f "$DEST" ] || [ "$(stat -c%s "$DEST" 2>/dev/null || echo 0)" != "$src_size" ]; then
    cp -f "$SRC" "$DEST" || exit 1
fi

# Docker starting up saturates the Pi, so ask for realtime like the stream player does.
# systemd's policy does not reach the child, hence chrt here. A buffer covers the rest.
RT_PLAYER="chrt -f 20 ionice -c1"
PLAYER_BUFFER_KB=1024
if ! command -v chrt >/dev/null || ! chrt -f 20 true 2>/dev/null; then
    echo "gimn: no realtime scheduling available, running normally" >&2
    RT_PLAYER=""
fi

while true; do
    # mpg123 has no inter-play gap of its own, so the pause lives here.
    if $RT_PLAYER mpg123 -q -b "$PLAYER_BUFFER_KB" "$DEST"; then
        sleep 3
    else
        echo "gimn: mpg123 exited $?, backing off" >&2
        sleep 5
    fi
done
