"""Синхронные DDL-операции на управляемых PostgreSQL-серверах.

Используется из Celery-задач (psycopg2, синхронный режим).
Все операции выполняются в БД postgres (admin database), не в целевой БД.
"""
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from app.models.server import Server
from app.services.crypto import decrypt


def _admin_conn(server: Server):
    """Открывает соединение к служебной БД postgres с autocommit."""
    password = decrypt(server.admin_password_encrypted)
    conn = psycopg2.connect(
        host=server.host,
        port=server.port,
        user=server.admin_user,
        password=password,
        dbname="postgres",
        connect_timeout=15,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def _db_conn(server: Server, database: str):
    """Соединение к КОНКРЕТНОЙ БД (а не postgres) с autocommit."""
    password = decrypt(server.admin_password_encrypted)
    conn = psycopg2.connect(
        host=server.host,
        port=server.port,
        user=server.admin_user,
        password=password,
        dbname=database,
        connect_timeout=15,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def terminate_connections(server: Server, database: str) -> int:
    """Завершает все подключения к database (кроме своего).

    Возвращает количество прерванных соединений.
    """
    conn = _admin_conn(server)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select count(pg_terminate_backend(pid))
                from pg_stat_activity
                where datname = %s
                  and pid <> pg_backend_pid()
                """,
                (database,),
            )
            row = cur.fetchone()
            return row[0] if row else 0
    finally:
        conn.close()


def database_exists(server: Server, database: str) -> bool:
    conn = _admin_conn(server)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select 1 from pg_database where datname = %s",
                (database,),
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


def rename_database(server: Server, old_name: str, new_name: str) -> None:
    """ALTER DATABASE old_name RENAME TO new_name."""
    conn = _admin_conn(server)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f'alter database "{old_name}" rename to "{new_name}"'
            )
    finally:
        conn.close()


def drop_database(server: Server, database: str) -> None:
    """DROP DATABASE IF EXISTS database."""
    conn = _admin_conn(server)
    try:
        with conn.cursor() as cur:
            cur.execute(f'drop database if exists "{database}"')
    finally:
        conn.close()


def list_databases_with_prefix(server: Server, prefix: str) -> list[str]:
    """Возвращает имена БД, начинающиеся с prefix (для чистки старых to_delete__)."""
    conn = _admin_conn(server)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "select datname from pg_database where datname like %s order by datname",
                (prefix + "%",),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def create_database(server: Server, database: str) -> None:
    """CREATE DATABASE database TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'."""
    conn = _admin_conn(server)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"create database \"{database}\""
                f" template template0"
                f" encoding 'UTF8'"
                f" lc_collate 'C'"
                f" lc_ctype 'C'"
            )
    finally:
        conn.close()


def list_database_extensions(server: Server, database: str) -> list[dict]:
    """Расширения, установленные в database (кроме plpgsql — он есть в template0).
    Порядок по oid = порядок установки (учитывает зависимости).
    Возвращает [{"name", "schema", "version"}, ...]."""
    conn = _db_conn(server, database)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select e.extname, n.nspname, e.extversion
                from pg_extension e
                join pg_namespace n on n.oid = e.extnamespace
                where e.extname <> 'plpgsql'
                order by e.oid
                """
            )
            return [{"name": r[0], "schema": r[1], "version": r[2]} for r in cur.fetchall()]
    finally:
        conn.close()


def ensure_extensions(server: Server, database: str, extensions: list[dict]) -> dict:
    """Пытается создать каждое расширение в целевой database (CREATE EXTENSION
    IF NOT EXISTS). НЕ бросает — возвращает
    {"created": [...], "existed": [...], "failed": [{"name", "error"}, ...]}.
    Различает «не установлено на сервере» (нет в pg_available_extensions) и прочие
    ошибки (напр. нет прав) — даёт реальную причину, а не каскад geometry-ошибок."""
    result: dict = {"created": [], "existed": [], "failed": []}
    if not extensions:
        return result
    conn = _db_conn(server, database)
    try:
        with conn.cursor() as cur:
            cur.execute("select extname from pg_extension")
            already = {r[0] for r in cur.fetchall()}
            cur.execute("select name from pg_available_extensions")
            available = {r[0] for r in cur.fetchall()}

        for ext in extensions:
            name = ext["name"]
            schema = ext.get("schema") or "public"
            if name in already:
                result["existed"].append(name)
                continue
            if name not in available:
                result["failed"].append({
                    "name": name,
                    "error": (
                        "не установлено на целевом сервере (нет в pg_available_extensions) — "
                        f"поставьте пакет расширения (напр. postgresql-<версия>-{name})"
                    ),
                })
                continue
            try:
                with conn.cursor() as cur:
                    if schema not in ("public", "pg_catalog"):
                        cur.execute(sql.SQL("create schema if not exists {}").format(
                            sql.Identifier(schema)))
                    cur.execute(sql.SQL("create extension if not exists {} with schema {}").format(
                        sql.Identifier(name), sql.Identifier(schema)))
                result["created"].append(name)
            except Exception as exc:  # noqa: BLE001
                raw = str(getattr(exc, "pgerror", None) or exc).strip()
                first = raw.splitlines()[0] if raw else "неизвестная ошибка"
                result["failed"].append({"name": name, "error": first})
        return result
    finally:
        conn.close()


def list_database_roles(server: Server, database: str) -> list[str]:
    """Роли, от которых зависят объекты database — владельцы И грантополучатели,
    через pg_shdepend (точный набор, нужный для restore). Без системных pg_*."""
    conn = _db_conn(server, database)
    try:
        with conn.cursor() as cur:
            cur.execute(
                r"""
                select distinct r.rolname
                from pg_shdepend s
                join pg_roles r on r.oid = s.refobjid
                where s.refclassid = 'pg_authid'::regclass
                  and s.dbid = (select oid from pg_database where datname = current_database())
                  and r.rolname not like 'pg\_%'
                order by 1
                """
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def ensure_roles(server: Server, database: str, roles: list[str]) -> dict:
    """Создаёт недостающие роли на ЦЕЛЕВОМ сервере (роли — кластерные, коннект к
    postgres). Создаём минимальные (NOLOGIN по умолчанию) — для владения объектами
    и грантов этого достаточно; пароли/атрибуты НЕ копируем (безопаснее).
    Возвращает {"created", "existed", "failed": [{"name", "error"}]}."""
    result: dict = {"created": [], "existed": [], "failed": []}
    if not roles:
        return result
    conn = _admin_conn(server)  # роли глобальны на кластер
    try:
        with conn.cursor() as cur:
            cur.execute("select rolname from pg_roles")
            existing = {r[0] for r in cur.fetchall()}
        for role in roles:
            if role in existing:
                result["existed"].append(role)
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute(sql.SQL("create role {}").format(sql.Identifier(role)))
                result["created"].append(role)
            except Exception as exc:  # noqa: BLE001
                raw = str(getattr(exc, "pgerror", None) or exc).strip()
                first = raw.splitlines()[0] if raw else "неизвестная ошибка"
                result["failed"].append({"name": role, "error": first})
        return result
    finally:
        conn.close()
