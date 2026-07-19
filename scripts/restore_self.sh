#!/usr/bin/env bash
set -euo pipefail

echo "=== DB Control Center — Self Restore ==="

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup_archive.tar.gz>"
  echo ""
  echo "Available backups:"
  ls -la self-backups/*.tar.gz 2>/dev/null || echo "  No backups found"
  exit 1
fi

ARCHIVE="$1"
if [ ! -f "$ARCHIVE" ]; then
  echo "ERROR: File not found: $ARCHIVE"
  exit 1
fi

cd "$(dirname "$0")/.."

TEMP_DIR=$(mktemp -d)
echo "Extracting to $TEMP_DIR..."
tar -xzf "$ARCHIVE" -C "$TEMP_DIR"

# Find the extracted directory
BACKUP_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d | tail -1)

echo ""
echo "WARNING: This will overwrite the current database!"
read -p "Continue? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  echo "Aborted."
  rm -rf "$TEMP_DIR"
  exit 0
fi

# Restore .env if present
if [ -f "${BACKUP_DIR}/.env" ]; then
  echo "Restoring .env..."
  cp "${BACKUP_DIR}/.env" .env
fi

# Restore appdb
if [ -f "${BACKUP_DIR}/appdb.sql" ]; then
  echo "Restoring appdb..."
  docker compose exec -T appdb psql -U pgadmin -d pgadmin -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null
  docker compose exec -T appdb psql -U pgadmin pgadmin < "${BACKUP_DIR}/appdb.sql"
  echo "  appdb restored"
fi

# Restore Redis
if [ -f "${BACKUP_DIR}/redis.rdb" ]; then
  echo "Restoring Redis..."
  docker compose stop redis
  docker compose cp "${BACKUP_DIR}/redis.rdb" redis:/data/dump.rdb 2>/dev/null || echo "  Redis restore skipped"
  docker compose start redis
fi

# Cleanup
rm -rf "$TEMP_DIR"

echo "Restarting services..."
docker compose restart backend worker scheduler

echo "=== Self restore complete ==="
