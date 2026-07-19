import json
from datetime import datetime, timezone

import redis as sync_redis

from app.config import settings
from app.models.server import Server
from app.services.pg_connection import execute_on_server

METRICS_CACHE_PREFIX = "pgadmin:metrics:"
METRICS_CACHE_TTL = 120

_PG_STAT_HINT = (
    "Нужно расширение pg_stat_statements: "
    "shared_preload_libraries = 'pg_stat_statements' в postgresql.conf, перезапуск PG, "
    "затем CREATE EXTENSION pg_stat_statements; в базе postgres."
)


def metrics_cache_key(server_id: int) -> str:
    return f"{METRICS_CACHE_PREFIX}{server_id}"


def _redis_client() -> sync_redis.Redis:
    return sync_redis.from_url(settings.redis_url)


def load_snapshot_from_redis(server_id: int) -> dict | None:
    try:
        r = _redis_client()
        raw = r.get(metrics_cache_key(server_id))
        r.close()
        if not raw:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict) or "connections" not in data:
            return None
        data["source"] = "redis"
        return data
    except Exception:
        return None


def save_snapshot_to_redis(server_id: int, snapshot: dict) -> None:
    payload = {**snapshot, "source": "redis"}
    payload["collected_at"] = datetime.now(timezone.utc).isoformat()
    try:
        r = _redis_client()
        r.set(
            metrics_cache_key(server_id),
            json.dumps(payload, default=str),
            ex=METRICS_CACHE_TTL,
        )
        r.close()
    except Exception:
        pass


async def _resolve_pg_major(server: Server) -> int:
    if server.pg_major_version:
        return server.pg_major_version
    rows = await execute_on_server(
        server,
        "select current_setting('server_version_num')::int / 10000 as major",
    )
    return int(rows[0]["major"]) if rows else 14


async def get_connection_stats(server: Server) -> dict:
    sql = """
    select
      count(*) as total,
      count(*) filter (where state = 'active') as active,
      count(*) filter (where state = 'idle') as idle,
      count(*) filter (where wait_event_type is not null and state = 'active') as waiting,
      (select setting::int from pg_settings where name = 'max_connections') as max_connections
    from pg_stat_activity
    where backend_type = 'client backend'
    """
    rows = await execute_on_server(server, sql)
    row = rows[0] if rows else {}
    return {
        "total": int(row.get("total") or 0),
        "active": int(row.get("active") or 0),
        "idle": int(row.get("idle") or 0),
        "waiting": int(row.get("waiting") or 0),
        "max_connections": int(row.get("max_connections") or 0),
    }


async def get_cache_hit_ratio(server: Server) -> float | None:
    sql = """
    select round(
      100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0),
      2
    ) as cache_hit_ratio
    from pg_stat_database
    where datname not in ('template0', 'template1')
    """
    rows = await execute_on_server(server, sql)
    if not rows:
        return None
    value = rows[0].get("cache_hit_ratio")
    if value is None:
        return None
    return float(value)


async def get_database_sizes(server: Server) -> list[dict]:
    sql = """
    select d.datname,
      pg_size_pretty(pg_database_size(d.datname)) as size,
      pg_database_size(d.datname) as size_bytes
    from pg_database d
    where d.datname not in ('template0', 'template1')
    order by pg_database_size(d.datname) desc
    """
    return await execute_on_server(server, sql)


async def get_storage_stats(server: Server) -> dict:
    total_rows = await execute_on_server(
        server,
        """
        select coalesce(sum(pg_database_size(datname)), 0)::bigint as total_db_bytes
        from pg_database
        where datname not in ('template0', 'template1')
        """,
    )
    ts_rows = await execute_on_server(
        server,
        """
        select spcname as name,
          pg_tablespace_size(oid) as size_bytes
        from pg_catalog.pg_tablespace
        order by pg_tablespace_size(oid) desc
        """,
    )
    return {
        "total_db_bytes": int(total_rows[0]["total_db_bytes"]) if total_rows else 0,
        "tablespaces": [
            {"name": row["name"], "size_bytes": int(row["size_bytes"] or 0)}
            for row in ts_rows
        ],
    }


async def get_slow_queries(server: Server, limit: int = 20) -> tuple[list[dict], dict]:
    meta: dict = {"available": False, "error": None, "hint": None}

    ext_rows = await execute_on_server(
        server,
        "select extname from pg_extension where extname = 'pg_stat_statements'",
    )
    if not ext_rows:
        meta["hint"] = _PG_STAT_HINT
        return [], meta

    major = await _resolve_pg_major(server)
    if major >= 13:
        mean_col, total_col = "mean_exec_time", "total_exec_time"
    else:
        mean_col, total_col = "mean_time", "total_time"

    sql = f"""
    select query,
      calls,
      round({mean_col}::numeric, 2) as mean_time_ms,
      round({total_col}::numeric, 2) as total_time_ms
    from pg_stat_statements
    order by {mean_col} desc
    limit {limit}
    """
    try:
        rows = await execute_on_server(server, sql)
        meta["available"] = True
        if not rows:
            meta["hint"] = "Расширение установлено, но статистика пуста (PG недавно перезапускали или нагрузки не было)."
        return rows, meta
    except Exception as exc:
        meta["error"] = str(exc)
        meta["hint"] = _PG_STAT_HINT
        return [], meta


async def get_locks(server: Server) -> list[dict]:
    sql = """
    select l.pid,
      c.relname as relation,
      l.mode,
      l.granted,
      a.query,
      age(now(), a.state_change)::text as wait_duration
    from pg_locks l
      left join pg_class c on c.oid = l.relation
      left join pg_stat_activity a on a.pid = l.pid
    where l.pid <> pg_backend_pid()
      and not l.granted
    order by a.state_change
    """
    return await execute_on_server(server, sql)


async def get_monitoring_snapshot(server: Server) -> dict:
    connections = await get_connection_stats(server)
    cache_hit_ratio = await get_cache_hit_ratio(server)
    db_sizes = await get_database_sizes(server)
    storage = await get_storage_stats(server)
    slow, slow_meta = await get_slow_queries(server)
    locks = await get_locks(server)
    now = datetime.now(timezone.utc).isoformat()
    return {
        "connections": connections,
        "cache_hit_ratio": cache_hit_ratio,
        "database_sizes": db_sizes,
        "storage": storage,
        "slow_queries": slow,
        "slow_queries_meta": slow_meta,
        "locks": locks,
        "collected_at": now,
        "source": "live",
    }


async def get_monitoring_for_api(server: Server, *, refresh: bool = False) -> dict:
    if not refresh:
        cached = load_snapshot_from_redis(server.id)
        if cached is not None:
            return cached
    snapshot = await get_monitoring_snapshot(server)
    save_snapshot_to_redis(server.id, snapshot)
    return snapshot
