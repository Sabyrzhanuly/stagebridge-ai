#!/usr/bin/env bash
set -euo pipefail

echo "=== DB Control Center — Upgrade ==="

cd "$(dirname "$0")/.."

echo "Pulling latest changes..."
git pull 2>/dev/null || echo "Not a git repo or no remote, skipping git pull"

echo "Building images..."
docker compose build

echo "Running migrations..."
docker compose exec -T backend alembic upgrade head 2>/dev/null || echo "Migrations skipped"

echo "Restarting services..."
docker compose up -d

echo "Waiting for services..."
sleep 5

echo "=== Upgrade complete ==="
docker compose ps
