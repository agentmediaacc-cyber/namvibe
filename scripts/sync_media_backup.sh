#!/usr/bin/env bash
set -euo pipefail

# Media files backup script for CHAIN
# Usage: ./scripts/sync_media_backup.sh [source_dir] [bucket]
# Requires: aws-cli or rclone configured

MEDIA_DIR="${1:-/var/www/chain_app/media}"
BUCKET="${2:-${BACKUP_BUCKET:-chain-backups}}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

if [ ! -d "$MEDIA_DIR" ]; then
  echo "WARNING: Media directory does not exist: $MEDIA_DIR" >&2
  echo "Nothing to sync. Exiting." >&2
  exit 0
fi

if command -v aws &>/dev/null; then
  aws s3 sync "$MEDIA_DIR" "s3://${BUCKET}/media/${TIMESTAMP}/" --no-progress
  echo "OK: synced $MEDIA_DIR to s3://${BUCKET}/media/${TIMESTAMP}/"
elif command -v rclone &>/dev/null; then
  rclone sync "$MEDIA_DIR" "remote:${BUCKET}/media/${TIMESTAMP}/" --progress
  echo "OK: synced $MEDIA_DIR to remote:${BUCKET}/media/${TIMESTAMP}/"
else
  echo "WARNING: Neither aws nor rclone found. Install one to enable media backup." >&2
  exit 0
fi
