#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 [+|-]<number>"
    exit 1
fi

current_vol=$(amixer get PCM | grep -oP '\[\d+%\]' | head -1 | tr -d '[]%')

if [ "$current_vol" -lt 45 ]; then
    current_vol=45
    amixer set PCM 45% > /dev/null
fi

change=$1
if [[ "$change" == +* ]]; then
    new_vol=$((current_vol + ${change:1}))
elif [[ "$change" == -* ]]; then
    new_vol=$((current_vol - ${change:1}))
else
    echo "Invalid input. Use +<number> or -<number>."
    exit 1
fi

if [ "$new_vol" -gt 95 ]; then
    new_vol=95
elif [ "$new_vol" -lt 45 ]; then
    new_vol=0
fi

amixer set PCM "${new_vol}%" > /dev/null

# 45% ALSA → 5, 95% → 100. Mute (0%) stays 0 after the clamp below.
vol_human=$(( (new_vol - 45) * 95 / 50 + 5 ))

if [ "$vol_human" -lt 0 ]; then
    vol_human=0
fi

echo "Volume set to ${vol_human} (${new_vol}% in alsa units)"
