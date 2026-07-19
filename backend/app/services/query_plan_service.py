"""Безопасное получение плана SELECT-запроса для консультативного ИИ-анализа."""

from __future__ import annotations

import asyncio
import json

import sqlparse
from sqlparse.tokens import DDL, DML

from app.models.server import Server
from app.services.pg_connection import get_target_pool


def is_explainable_query(query: str) -> bool:
    if not isinstance(query, str) or not query.strip() or len(query) > 50_000:
        return False
    statements = [statement for statement in sqlparse.parse(query) if str(statement).strip()]
    if len(statements) != 1 or statements[0].get_type() != "SELECT":
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
