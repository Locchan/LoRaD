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

while true; do
    # mpg123 has no inter-play gap of its own, so the pause lives here.
    if mpg123 -q "$DEST"; then
        sleep 3
    else
        echo "gimn: mpg123 exited $?, backing off" >&2
        sleep 5
    fi
done
