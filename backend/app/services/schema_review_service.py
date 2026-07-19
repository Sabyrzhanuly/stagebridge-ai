"""Компактный read-only снимок схемы БД для advisory AI review."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from app.models.server import Server
from app.services.pg_connection import get_target_pool

MAX_TABLES = 40
MAX_COLUMNS = 500
MAX_FOREIGN_KEYS = 160
MAX_INDEXES = 200
MAX_TEXT = 600


def _truncate(value: Any, limit: int = MAX_TEXT) -> Any:
    if not isinstance(value, str) or len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _row_dict(row: Any) -> dict:
    data = dict(row)
    return {key: _truncate(value) for key, value in data.items()}


async def collect_schema_metadata(
    server: Server,
    database: str,
    *,
    max_tables: int = MAX_TABLES,
    timeout_ms: int = 3_000,
) -> dict:
    table_limit = max(1, min(max_tables, MAX_TABLES))
    pool = await get_target_pool(server, database)
    try:
        async with asyncio.timeout(timeout_ms / 1000 + 1):
            async with pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    await conn.execute(
                        "select set_config('statement_timeout', $1, true)",
                        f"{timeout_ms}ms",
                    )
                    tables = [
                        _row_dict(row)
                        for row in await conn.fetch(
                            """
                            select
                              n.nspname as schema_name,
                              c.relname as table_name,
                              case c.relkind when 'p' then 'partitioned' else 'table' end as table_kind,
                              greatest(c.reltuples, 0)::bigint as row_estimate,
                              pg_total_relation_size(c.oid) as total_bytes
                            from pg_catalog.pg_class c
                              join pg_catalog.pg_namespace n on n.oid = c.relnamespace
                            where c.relkind in ('r', 'p')
                              and n.nspname not in ('pg_catalog', 'information_schema')
                              and n.nspname not like 'pg_toast%'
                              and n.nspname not like 'pg_temp%'
                            order by pg_total_relation_size(c.oid) desc, c.reltuples desc, n.nspname, c.relname
                            limit $1
                            """,
                            table_limit,
                        )
                    ]
                    schemas = [row["schema_name"] for row in tables]
                    names = [row["table_name"] for row in tables]
                    columns = await _fetch_columns(conn, schemas, names)
                    primary_keys = await _fetch_primary_keys(conn, schemas, names)
                    foreign_keys = await _fetch_foreign_keys(conn, schemas, names)
                    indexes = await _fetch_indexes(conn, schemas, names)
    finally:
        await pool.close()

    return {
        "database": database,
        "limits": {
            "max_tables": table_limit,
            "max_columns": MAX_COLUMNS,
            "max_foreign_keys": MAX_FOREIGN_KEYS,
            "max_indexes": MAX_INDEXES,
        },
        "tables": tables,
        "columns": columns,
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
    }


async def _fetch_columns(conn, schemas: list[str], names: list[str]) -> list[dict]:
    if not schemas:
        return []
    rows = await conn.fetch(
        """
        with selected(schema_name, table_name) as (
          select * from unnest($1::text[], $2::text[])
        )
        select
          c.table_schema as schema_name,
          c.table_name,
          c.column_name,
          c.ordinal_position,
          c.data_type,
          c.udt_name,
          c.is_nullable = 'YES' as nullable,
          c.column_default,
          c.character_maximum_length,
          c.numeric_precision,
          c.numeric_scale
        from information_schema.columns c
          join selected s on s.schema_name = c.table_schema and s.table_name = c.table_name
        order by c.table_schema, c.table_name, c.ordinal_position
        limit $3
        """,
        schemas,
        names,
        MAX_COLUMNS,
    )
    return [_row_dict(row) for row in rows]


async def _fetch_primary_keys(conn, schemas: list[str], names: list[str]) -> list[dict]:
    if not schemas:
        return []
    rows = await conn.fetch(
        """
        with selected(schema_name, table_name) as (
          select * from unnest($1::text[], $2::text[])
        )
        select
          tc.table_schema as schema_name,
          tc.table_name,
          tc.constraint_name,
          array_agg(kcu.column_name order by kcu.ordinal_position) as columns
        from information_schema.table_constraints tc
          join information_schema.key_column_usage kcu
            on kcu.constraint_schema = tc.constraint_schema
           and kcu.constraint_name = tc.constraint_name
           and kcu.table_schema = tc.table_schema
           and kcu.table_name = tc.table_name
          join selected s on s.schema_name = tc.table_schema and s.table_name = tc.table_name
        where tc.constraint_type = 'PRIMARY KEY'
        group by tc.table_schema, tc.table_name, tc.constraint_name
        order by tc.table_schema, tc.table_name, tc.constraint_name
        """,
        schemas,
        names,
    )
    return [_row_dict(row) for row in rows]


async def _fetch_foreign_keys(conn, schemas: list[str], names: list[str]) -> list[dict]:
    if not schemas:
        return []
    rows = await conn.fetch(
        """
        with selected(schema_name, table_name) as (
          select * from unnest($1::text[], $2::text[])
        )
        select
          tc.table_schema as schema_name,
          tc.table_name,
          tc.constraint_name,
          kcu.column_name,
          ccu.table_schema as foreign_schema_name,
          ccu.table_name as foreign_table_name,
          ccu.column_name as foreign_column_name
        from information_schema.table_constraints tc
          join information_schema.key_column_usage kcu
            on kcu.constraint_schema = tc.constraint_schema
           and kcu.constraint_name = tc.constraint_name
           and kcu.table_schema = tc.table_schema
           and kcu.table_name = tc.table_name
          join information_schema.constraint_column_usage ccu
            on ccu.constraint_schema = tc.constraint_schema
           and ccu.constraint_name = tc.constraint_name
          join selected s on s.schema_name = tc.table_schema and s.table_name = tc.table_name
        where tc.constraint_type = 'FOREIGN KEY'
        order by tc.table_schema, tc.table_name, tc.constraint_name, kcu.ordinal_position
        limit $3
        """,
        schemas,
        names,
        MAX_FOREIGN_KEYS,
    )
    grouped: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        data = _row_dict(row)
        key = (data["schema_name"], data["table_name"], data["constraint_name"])
        item = grouped.setdefault(
            key,
            {
                "schema_name": data["schema_name"],
                "table_name": data["table_name"],
                "constraint_name": data["constraint_name"],
                "columns": [],
                "foreign_table": f"{data['foreign_schema_name']}.{data['foreign_table_name']}",
                "foreign_columns": [],
            },
        )
        item["columns"].append(data["column_name"])
        item["foreign_columns"].append(data["foreign_column_name"])
    return list(grouped.values())


async def _fetch_indexes(conn, schemas: list[str], names: list[str]) -> list[dict]:
    if not schemas:
        return []
    rows = await conn.fetch(
        """
        with selected(schema_name, table_name) as (
          select * from unnest($1::text[], $2::text[])
        )
        select
          i.schemaname as schema_name,
          i.tablename as table_name,
          i.indexname as index_name,
          i.indexdef as index_def
        from pg_catalog.pg_indexes i
          join selected s on s.schema_name = i.schemaname and s.table_name = i.tablename
        order by i.schemaname, i.tablename, i.indexname
        limit $3
        """,
        schemas,
        names,
        MAX_INDEXES,
    )
    by_table: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        data = _row_dict(row)
        by_table[f"{data['schema_name']}.{data['table_name']}"].append(
            {
                "index_name": data["index_name"],
                "index_def": data["index_def"],
            }
        )
    return [{"table": table, "indexes": indexes} for table, indexes in by_table.items()]
