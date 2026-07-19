"""Безопасное получение плана SELECT-запроса для консультативного ИИ-анализа."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import sqlparse
from sqlparse.tokens import DDL, DML

from app.models.server import Server
from app.services.pg_connection import get_target_pool

MAX_RESULT_ROWS = 100
MAX_CELL_TEXT = 500


def is_explainable_query(query: str) -> bool:
    if not isinstance(query, str) or not query.strip() or len(query) > 50_000:
        return False
    statements = [statement for statement in sqlparse.parse(query) if str(statement).strip()]
    if len(statements) != 1 or statements[0].get_type() != "SELECT":
        return False
    normalized = " ".join(str(statements[0]).lower().split())
    if any(
        clause in normalized
        for clause in (
            " for update",
            " for no key update",
            " for share",
            " for key share",
        )
    ):
        return False
    for token in statements[0].flatten():
        if token.ttype in DDL:
            return False
        if token.ttype in DML and token.normalized != "SELECT":
            return False
    return True


async def explain_query(
    server: Server,
    query: str,
    database: str = "postgres",
    *,
    timeout_ms: int = 2_000,
) -> object | None:
    """Вернуть JSON-план без выполнения запроса или None для небезопасного SQL."""
    if not is_explainable_query(query):
        return None

    pool = await get_target_pool(server, database)
    try:
        async with asyncio.timeout(timeout_ms / 1000 + 1):
            async with pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    await conn.execute(
                        "select set_config('statement_timeout', $1, true)",
                        f"{timeout_ms}ms",
                    )
                    rows = await conn.fetch(f"EXPLAIN (FORMAT JSON) {query}")
        if not rows:
            return None
        plan = rows[0][0]
        return json.loads(plan) if isinstance(plan, str) else plan
    finally:
        await pool.close()


def _strip_trailing_semicolon(query: str) -> str:
    sql = query.strip()
    while sql.endswith(";"):
        sql = sql[:-1].rstrip()
    return sql


def _cell(value: Any, limit: int = MAX_CELL_TEXT) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


async def run_readonly_select(
    server: Server,
    query: str,
    database: str = "postgres",
    *,
    timeout_ms: int = 3_000,
    row_limit: int = MAX_RESULT_ROWS,
) -> dict:
    """Выполнить только заранее проверенный SELECT с жесткими runtime-ограничениями."""
    if not is_explainable_query(query):
        raise ValueError("not a safe read-only SELECT")

    safe_timeout_ms = max(1, min(timeout_ms, 3_000))
    safe_row_limit = max(1, min(row_limit, MAX_RESULT_ROWS))
    inner_sql = _strip_trailing_semicolon(query)
    wrapped_sql = f"SELECT * FROM (\n{inner_sql}\n) _q LIMIT {safe_row_limit}"

    pool = await get_target_pool(server, database)
    try:
        async with asyncio.timeout(safe_timeout_ms / 1000 + 1):
            async with pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    await conn.execute(
                        "select set_config('statement_timeout', $1, true)",
                        f"{safe_timeout_ms}ms",
                    )
                    fetched = await conn.fetch(wrapped_sql)
        columns = list(fetched[0].keys()) if fetched else []
        rows = [
            {column: _cell(row[column]) for column in row.keys()}
            for row in fetched[:safe_row_limit]
        ]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
    finally:
        await pool.close()
