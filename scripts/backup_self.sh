#!/usr/bin/env bash
set -euo pipefail

echo "=== DB Control Center — Self Backup ==="

cd "$(dirname "$0")/.."

BACKUP_DIR="./self-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"

mkdir -p "$BACKUP_PATH"

# Backup appdb
echo "Backing up appdb..."
docker compose exec -T appdb pg_dump -U pgadmin pgadmin > "${BACKUP_PATH}/appdb.sql"
echo "  appdb.sql: $(wc -c < "${BACKUP_PATH}/appdb.sql") bytes"

# Backup Redis
echo "Backing up Redis..."
docker compose exec -T redis redis-cli BGSAVE >/dev/null 2>&1
sleep 2
docker compose cp redis:/data/dump.rdb "${BACKUP_PATH}/redis.rdb" 2>/dev/null || echo "  Redis dump not available"

# Backup .env
echo "Backing up .env..."
cp .env "${BACKUP_PATH}/.env"

# Backup docker-compose.yml
cp docker-compose.yml "${BACKUP_PATH}/docker-compose.yml"

# Archive
echo "Creating archive..."
tar -czf "${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz" -C "$BACKUP_DIR" "$TIMESTAMP"
rm -rf "$BACKUP_PATH"

echo "=== Self backup complete ==="
echo "File: ${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz"
echo "Size: $(du -h "${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz" | cut -f1)"
