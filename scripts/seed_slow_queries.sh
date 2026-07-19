#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

cd "$REPO_ROOT"

docker compose exec -T demopg \
  psql -v ON_ERROR_STOP=1 \
  -U "${DEMO_PG_USER:-postgres}" \
  -d "${DEMO_PG_DATABASE:-demo_shop}" \
  < infra/demopg-init/003-slow-query-demo.sql

docker compose exec -T demopg \
  psql -v ON_ERROR_STOP=1 \
  -U "${DEMO_PG_USER:-postgres}" \
  -d "${DEMO_PG_DATABASE:-demo_shop}" \
  -c "SELECT calls, round(mean_exec_time::numeric, 2) AS mean_ms, left(query, 100) AS query FROM pg_stat_statements WHERE query LIKE '%demo_perf_%' ORDER BY mean_exec_time DESC LIMIT 8"
