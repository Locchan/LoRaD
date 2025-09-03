#!/bin/bash

LAST_COMMIT_DATE=$(git log -1 --date=format:"%d.%m.%Y %T" --format="%ad")
LAST_COMMIT_HASH=$(git log --pretty=format:'%h' -n 1)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
LAST_COMMIT_NUMBER=$(git rev-list --count $CURRENT_BRANCH)
LORAD_VERSION=$(sed -nE 's/version = "(.*)"/\1/p' pyproject.toml)
LORAD_FRONT_VERSION=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' frontend/package.json)
LOC=$(find . -name "*.py" -exec cat {} + | wc -l )

while test $# -gt 0
do
    case "$1" in
        --short) echo "$LORAD_VERSION.$LAST_COMMIT_NUMBER";
        exit 0
            ;;
    esac
    case "$1" in
        --frontend) echo "$LORAD_FRONT_VERSION.$LAST_COMMIT_NUMBER";
        exit 0
            ;;
    esac
    shift
done

echo "LoRaD v.$LORAD_VERSION.$LAST_COMMIT_NUMBER | Commit: $LAST_COMMIT_HASH; $LAST_COMMIT_DATE | $LOC LoC"

exit 0