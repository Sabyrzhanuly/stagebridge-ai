from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import psycopg
from django.utils import timezone
from psycopg.rows import dict_row

from analysis.models import ConnectionProfile
from .localization import translate

DatabaseTarget = Literal["prod", "dev", "stage", "dryrun"]

DEFAULT_DATABASES: dict[DatabaseTarget, str] = {
    "prod": "stagebridge_prod",
    "dev": "stagebridge_dev",
    "stage": "stagebridge_stage",
    "dryrun": "stagebridge_dryrun",
}

TARGET_LABELS: dict[DatabaseTarget, str] = {
    "prod": "Production demo",
    "dev": "Development demo",
    "stage": "Staging demo",
    "dryrun": "Dry run demo",
}

ALLOWED_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "host.docker.internal"}


@dataclass(frozen=True)
class DatabaseConfig:
    target: DatabaseTarget
    label: str
    host: str
    port: int
    name: str
    user: str
    password_set: bool
    read_only: bool

    def public_dict(self, locale: str = "ru") -> dict[str, object]:
        return {
            "id": f"demo-{self.target}",
            "target": self.target,
            "name": translate(f"connections.labels.{self.target}", locale),
            "role": _target_role(self.target),
            "host": self.host,
            "port": self.port,
            "database": self.name,
            "username": self.user,
            "passwordSet": self.password_set,
            "readOnly": self.read_only,
            "sslmode": "prefer",
            "selected_schemas": ["public"],
            "statement_timeout": int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "5000")),
            "last_test_status": "demo",
            "last_test_message": translate("connections.demo_seeded", locale),
            "last_tested_at": None,
            "is_demo": True,
        }


def _target_role(target: DatabaseTarget) -> str:
    return {"prod": "production", "dev": "development", "stage": "staging", "dryrun": "staging"}[target]


def _prefix(target: DatabaseTarget) -> str:
    return f"{target.upper()}_DB"


def get_database_config(target: DatabaseTarget) -> DatabaseConfig:
    prefix = _prefix(target)
    password = os.getenv(f"{prefix}_PASSWORD", os.getenv("POSTGRES_PASSWORD", "stagebridge"))
    return DatabaseConfig(
        target=target,
        label=TARGET_LABELS[target],
        host=os.getenv(f"{prefix}_HOST", os.getenv("POSTGRES_HOST", "localhost")),
        port=int(os.getenv(f"{prefix}_PORT", os.getenv("POSTGRES_PORT", "5432"))),
        name=os.getenv(f"{prefix}_NAME", DEFAULT_DATABASES[target]),
        user=os.getenv(f"{prefix}_USER", os.getenv("POSTGRES_USER", "stagebridge")),
        password_set=bool(password),
        read_only=target in {"prod", "dev", "stage"},
    )


def list_demo_database_configs(locale: str = "ru") -> list[dict[str, object]]:
    return [get_database_config(target).public_dict(locale) for target in ("prod", "dev", "stage")]


def external_hosts_enabled() -> bool:
    return os.getenv("ALLOW_EXTERNAL_DB_HOSTS", "0") == "1"


def assert_host_allowed(host: str) -> None:
    if external_hosts_enabled() or host.lower() in ALLOWED_LOCAL_HOSTS:
        return
    raise ValueError(
        f"External database host '{host}' is disabled. Set ALLOW_EXTERNAL_DB_HOSTS=1 on the backend to enable it explicitly."
    )


def _connect(*, host: str, port: int, database: str, username: str, password: str, sslmode: str, connect_timeout: int, autocommit: bool):
    assert_host_allowed(host)
    return psycopg.connect(
        host=host,
        port=port,
        dbname=database,
        user=username,
        password=password,
        sslmode=sslmode,
        autocommit=autocommit,
        row_factory=dict_row,
        connect_timeout=connect_timeout,
    )


def connect_to_target(target: DatabaseTarget, *, read_only: bool | None = None, autocommit: bool = True):
    config = get_database_config(target)
    prefix = _prefix(target)
    password = os.getenv(f"{prefix}_PASSWORD", os.getenv("POSTGRES_PASSWORD", "stagebridge"))
    conn = _connect(
        host=config.host,
        port=config.port,
        database=config.name,
        username=config.user,
        password=password,
        sslmode=os.getenv(f"{prefix}_SSLMODE", "prefer"),
        connect_timeout=5,
        autocommit=autocommit,
    )
    timeout_ms = str(int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "5000")))
    conn.execute("SELECT set_config('statement_timeout', %s, false)", (timeout_ms,))
    if read_only if read_only is not None else config.read_only:
        conn.execute("SET default_transaction_read_only TO on")
    return conn


def connect_to_profile(profile: ConnectionProfile):
    """Open one explicit read-only transaction for all live inspection work."""
    conn = _connect(
        host=profile.host,
        port=profile.port,
        database=profile.database,
        username=profile.username,
        password=profile.password,
        sslmode=profile.sslmode,
        connect_timeout=5,
        autocommit=False,
    )
    conn.execute("SET TRANSACTION READ ONLY")
    conn.execute("SELECT set_config('statement_timeout', %s, true)", (str(profile.statement_timeout),))
    return conn


def connect_to_profile_writable(profile: ConnectionProfile):
    """Открыть транзакционное записываемое соединение к целевой staging-базе.

    Используется ТОЛЬКО для наката в staging-профиль: одна транзакция на весь
    сценарий, при ошибке — полный откат. Statement timeout ограничивает запросы.
    """
    conn = _connect(
        host=profile.host,
        port=profile.port,
        database=profile.database,
        username=profile.username,
        password=profile.password,
        sslmode=profile.sslmode,
        connect_timeout=5,
        autocommit=False,
    )
    conn.execute("SELECT set_config('statement_timeout', %s, true)", (str(profile.statement_timeout),))
    return conn


def available_schemas(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND schema_name NOT LIKE 'pg_temp_%'
          AND schema_name NOT LIKE 'pg_toast_temp_%'
        ORDER BY schema_name
        """
    ).fetchall()
    return [row["schema_name"] for row in rows]


def _probe_connection(conn):
    """Единый зонд соединения: имя БД, пользователь, режим чтения и версия сервера."""
    return conn.execute(
        "SELECT current_database() AS database_name, current_user AS user_name, "
        "current_setting('transaction_read_only') AS read_only, "
        "current_setting('server_version') AS server_version"
    ).fetchone()


def test_adhoc_connection(params: dict, locale: str = "ru") -> dict[str, object]:
    """Проверить произвольные параметры подключения ДО сохранения профиля.

    Как «Добавить сервер» в pgadmin: вводишь параметры → тест → видишь версию и
    доступные схемы. Соединение read-only и закрывается сразу. Хост проходит
    allowlist через :func:`_connect`.
    """
    try:
        conn = _connect(
            host=str(params.get("host") or ""),
            port=int(params.get("port") or 5432),
            database=str(params.get("database") or ""),
            username=str(params.get("username") or ""),
            password=str(params.get("password") or ""),
            sslmode=str(params.get("sslmode") or "prefer"),
            connect_timeout=5,
            autocommit=True,
        )
        try:
            conn.execute("SET default_transaction_read_only TO on")
            conn.execute("SELECT set_config('statement_timeout', %s, false)", (str(int(params.get("statement_timeout") or 5000)),))
            row = _probe_connection(conn)
            schemas = available_schemas(conn)
        finally:
            conn.close()
        return {
            "ok": True,
            "database": row["database_name"],
            "user": row["user_name"],
            "readOnly": row["read_only"] == "on",
            "serverVersion": row["server_version"],
            "schemas": schemas,
            "message": translate("connections.connected", locale, database=row["database_name"], user=row["user_name"]),
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "message": str(exc), "schemas": [], "serverVersion": ""}


def test_database_connection(target: DatabaseTarget, locale: str = "ru") -> dict[str, object]:
    config = get_database_config(target)
    try:
        with connect_to_target(target, read_only=config.read_only) as conn:
            row = _probe_connection(conn)
            schemas = available_schemas(conn)
        return {
            "ok": True,
            "target": target,
            "database": row["database_name"],
            "user": row["user_name"],
            "readOnly": row["read_only"] == "on",
            "serverVersion": row["server_version"],
            "schemas": schemas,
            "message": translate("connections.connected", locale, database=row["database_name"], user=row["user_name"]),
            "error": "",
        }
    except Exception as exc:
        return {"ok": False, "target": target, "database": config.name, "user": config.user, "error": str(exc), "message": str(exc)}


def test_profile_connection(profile: ConnectionProfile, locale: str = "ru") -> dict[str, object]:
    try:
        with connect_to_profile(profile) as conn:
            row = _probe_connection(conn)
            schemas = available_schemas(conn)
        message = translate("connections.connected", locale, database=row["database_name"], user=row["user_name"])
        profile.last_test_status = "connected"
        profile.last_test_message = message
        profile.last_tested_at = timezone.now()
        profile.save(update_fields=["last_test_status", "last_test_message", "last_tested_at", "updated_at"])
        return {
            "ok": True,
            "connection_id": profile.id,
            "database": row["database_name"],
            "user": row["user_name"],
            "readOnly": row["read_only"] == "on",
            "serverVersion": row["server_version"],
            "schemas": schemas,
            "message": message,
            "error": "",
        }
    except Exception as exc:
        message = str(exc)
        profile.last_test_status = "failed"
        profile.last_test_message = message
        profile.last_tested_at = timezone.now()
        profile.save(update_fields=["last_test_status", "last_test_message", "last_tested_at", "updated_at"])
        return {
            "ok": False,
            "connection_id": profile.id,
            "database": profile.database,
            "user": profile.username,
            "readOnly": True,
            "schemas": [],
            "message": message,
            "error": message,
        }


def profile_snapshot(profile: ConnectionProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "role": profile.role,
        "host": profile.host,
        "port": profile.port,
        "database": profile.database,
        "username": profile.username,
        "sslmode": profile.sslmode,
        "selected_schemas": list(profile.selected_schemas or []),
        "statement_timeout": profile.statement_timeout,
        "readOnly": True,
    }
