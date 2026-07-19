import re

from app.models.server import Server
from app.services.pg_connection import execute_on_server, get_target_pool

_HBA_SQL = """
select
  line_number,
  type,
  database,
  user_name,
  address,
  netmask,
  auth_method,
  options,
  error
from pg_hba_file_rules
order by line_number
"""

_SETTINGS_BASE_SQL = """
select
  name,
  setting,
  unit,
  category,
  context,
  source
from pg_settings
order by name
"""


def _join_names(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return str(value)


async def _fetchval(server: Server, sql: str) -> str | None:
    pool = await get_target_pool(server)
    try:
        async with pool.acquire() as conn:
            val = await conn.fetchval(sql)
            return None if val is None else str(val)
    finally:
        await pool.close()


async def _pg_major(server: Server) -> int:
    """Major-версия только с живого подключения (кэш в servers не используем для SQL)."""
    raw = await _fetchval(server, "show server_version_num")
    if raw and raw.strip().isdigit():
        return int(raw.strip()) // 10000

    raw = await _fetchval(server, "select current_setting('server_version_num')")
    if raw and raw.strip().isdigit():
        return int(raw.strip()) // 10000

    version_str = await _fetchval(server, "select version()")
    if version_str:
        match = re.search(r"PostgreSQL\s+(\d+)", version_str)
        if match:
            return int(match.group(1))

    return 12


def _map_hba(row: dict, hba_file: str | None) -> dict:
    line = row.get("line_number")
    return {
        "rule_number": line,
        "file_name": hba_file,
        "line_number": line,
        "type": row.get("type") or "",
        "databases": _join_names(row.get("database")),
        "users": _join_names(row.get("user_name")),
        "address": row.get("address"),
        "netmask": row.get("netmask"),
        "auth_method": row.get("auth_method"),
        "options": _join_names(row.get("options")),
        "error": row.get("error"),
    }


def _map_setting(row: dict) -> dict:
    return {
        "name": row.get("name") or "",
        "setting": row.get("setting"),
        "unit": row.get("unit"),
        "category": row.get("category"),
        "context": row.get("context"),
        "source": row.get("source"),
        "sourcefile": row.get("sourcefile"),
        "sourceline": row.get("sourceline"),
        "pending_restart": row.get("pending_restart"),
    }


async def _fetch_settings(server: Server) -> list[dict]:
    rows = await execute_on_server(server, _SETTINGS_BASE_SQL)
    by_name = {row["name"]: _map_setting(row) for row in rows}

    # PG 13+: pending_restart; PG 14+: sourcefile, sourceline — подгружаем отдельно, без падения
    extra_cols: list[str] = []
    try:
        probe = await execute_on_server(
            server,
            "select pending_restart from pg_settings where name = 'max_connections' limit 1",
        )
        if probe:
            extra_cols.append("pending_restart")
    except Exception:
        pass

    for col in ("sourcefile", "sourceline"):
        try:
            await execute_on_server(
                server,
                f"select {col} from pg_settings where name = 'max_connections' limit 1",
            )
            extra_cols.append(col)
        except Exception:
            break

    if extra_cols:
        col_list = ", ".join(["name", *extra_cols])
        try:
            extra_rows = await execute_on_server(
                server,
                f"select {col_list} from pg_settings",
            )
            for row in extra_rows:
                name = row.get("name")
                if name in by_name:
                    for col in extra_cols:
                        by_name[name][col] = row.get(col)
        except Exception:
            pass

    return list(by_name.values())


async def get_pg_config(server: Server) -> dict:
    pg_major = await _pg_major(server)

    is_superuser = bool(
        await _fetchval(
            server,
            "select usesuper from pg_catalog.pg_user where usename = current_user",
        )
    )

    config_file = await _fetchval(server, "show config_file")
    hba_file = await _fetchval(server, "show hba_file")

    settings = await _fetch_settings(server)

    file_settings = None
    file_settings_error = None
    try:
        file_settings_rows = await execute_on_server(
            server,
            """
            select
              sourcefile,
              sourceline,
              seqno,
              name,
              setting,
              applied,
              error
            from pg_file_settings
            order by sourcefile, sourceline, seqno
            """,
        )
        file_settings = [
            {
                "sourcefile": row.get("sourcefile"),
                "sourceline": row.get("sourceline"),
                "seqno": row.get("seqno"),
                "name": row.get("name") or "",
                "setting": row.get("setting"),
                "applied": bool(row.get("applied")),
                "error": row.get("error"),
            }
            for row in file_settings_rows
        ]
    except Exception as exc:
        file_settings_error = str(exc)

    hba_rules = None
    hba_error = None
    try:
        hba_rows = await execute_on_server(server, _HBA_SQL)
        hba_rules = [_map_hba(row, hba_file) for row in hba_rows]
    except Exception as exc:
        hba_error = str(exc)

    return {
        "server_name": server.name,
        "pg_major_version": pg_major,
        "is_superuser": is_superuser,
        "paths": {
            "config_file": config_file,
            "hba_file": hba_file,
        },
        "settings": settings,
        "file_settings": file_settings,
        "file_settings_error": file_settings_error,
        "hba_rules": hba_rules,
        "hba_error": hba_error,
    }
