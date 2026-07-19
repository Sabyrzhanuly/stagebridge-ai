import asyncpg

from app.models.server import Server
from app.services.crypto import decrypt


def quote_ident(name: str) -> str:
    """Безопасно квотирует SQL-идентификатор (роль/БД/схема) — защита от инъекции.

    Идентификаторы нельзя параметризовать ($1), поэтому оборачиваем в двойные
    кавычки с экранированием. Имя вида 'x"; drop database ...' станет одним
    (пусть и странным) идентификатором, а не набором операторов.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Пустой SQL-идентификатор")
    if "\x00" in name:
        raise ValueError("Недопустимый идентификатор (null-байт)")
    if len(name.encode("utf-8")) > 63:
        raise ValueError(f"Слишком длинный SQL-идентификатор: {name!r}")
    return '"' + name.replace('"', '""') + '"'


async def get_target_pool(server: Server, database: str = "postgres") -> asyncpg.Pool:
    password = decrypt(server.admin_password_encrypted)
    return await asyncpg.create_pool(
        host=server.host,
        port=server.port,
        user=server.admin_user,
        password=password,
        database=database,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )


def _parse_pg_major(version_str: str) -> int | None:
    """Извлекает major-версию из строки вида 'PostgreSQL 12.18 ...'"""
    import re
    m = re.search(r'PostgreSQL\s+(\d+)', version_str or '')
    if m:
        return int(m.group(1))
    return None


async def test_connection(host: str, port: int, user: str, password: str) -> tuple[bool, str | None, str | None, int | None]:
    try:
        conn = await asyncpg.connect(
            host=host, port=port, user=user, password=password, database="postgres", timeout=10
        )
        version = await conn.fetchval("select version()")
        await conn.close()
        return True, version, None, _parse_pg_major(version)
    except Exception as e:
        return False, None, str(e), None


async def execute_on_server(server: Server, sql: str, database: str = "postgres", *args) -> list[dict]:
    # *args → параметры запроса ($1, $2 …) для безопасной подстановки ЗНАЧЕНИЙ.
    pool = await get_target_pool(server, database)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]
    finally:
        await pool.close()


async def execute_command(server: Server, sql: str, database: str = "postgres", *args) -> str:
    pool = await get_target_pool(server, database)
    try:
        async with pool.acquire() as conn:
            return await conn.execute(sql, *args)
    finally:
        await pool.close()
