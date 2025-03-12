LAST_COMMIT_DATE=$(git log -1 --date=format:"%Y/%m/%d %T" --format="%ad")
LAST_COMMIT_HASH=$(git log --pretty=format:'%h' -n 1)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
LAST_COMMIT_NUMBER=$(git rev-list --count $CURRENT_BRANCH)
LORAD_VERSION=$(sed -nE 's/version = "(.*)"/\1/p' pyproject.toml)

echo "LoRaD v.$LORAD_VERSION.$LAST_COMMIT_NUMBER (Commit: $LAST_COMMIT_HASH; $LAST_COMMIT_DATE)"