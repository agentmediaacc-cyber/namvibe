#!/usr/bin/env bash
set -euo pipefail

# Database backup script for CHAIN
# Usage: ./scripts/backup_db.sh [output_dir]
# Requires: DATABASE_URL env var, pg_dump

OUTPUT_DIR="${1:-${CHAIN_BACKUP_LOCATION:-/var/backups/chain}}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${OUTPUT_DIR}/chain_db_${TIMESTAMP}.sql.gz"
LATEST_LINK="${OUTPUT_DIR}/chain_db_latest.sql.gz"

mkdir -p "$OUTPUT_DIR"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set" >&2
  exit 1
fi

pg_dump "$DATABASE_URL" --no-owner --no-acl | gzip > "$BACKUP_FILE"
ln -sf "$BACKUP_FILE" "$LATEST_LINK"

echo "OK: backup written to $BACKUP_FILE"
