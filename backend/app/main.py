from contextlib import asynccontextmanager
import asyncio
from datetime import datetime

import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import update

# Алиас: имя settings ниже занято роутером app.api.settings.
from app.config import settings as app_settings

from app.database import engine, Base, AsyncSessionLocal
from app.api import auth, servers, roles, databases, backups, monitoring, diagnostics, notifications, ws, audit, settings, scenarios, cron_schedules, organizations, admin, s3_storages, pg_config, structure_sync, ai


async def _migrate_excluded_tables() -> None:
    """Добавляет колонку excluded_tables_json если её нет (одноразовая миграция)."""
    import asyncio
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(
                conn.execute(text(
                    "ALTER TABLE restore_scenarios "
                    "ADD COLUMN IF NOT EXISTS excluded_tables_json TEXT DEFAULT '[]'"
                )),
                timeout=5.0,
            )
            await asyncio.wait_for(
                conn.execute(text(
                    "ALTER TABLE structure_sync_scenarios "
                    "ADD COLUMN IF NOT EXISTS excluded_tables_json TEXT DEFAULT '[]'"
                )),
                timeout=5.0,
            )
            await conn.commit()
        print("[startup] Миграция excluded_tables_json: OK")
    except asyncio.TimeoutError:
        print("[startup] Миграция: таймаут — колонка, вероятно, уже существует или заблокирована")
    except Exception as e:
        print(f"[startup] Миграция excluded_tables_json: {e}")


async def _migrate_pg_major_version() -> None:
    """Добавляет pg_major_version в servers если её нет."""
    import asyncio
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(
                conn.execute(text(
                    "ALTER TABLE servers "
                    "ADD COLUMN IF NOT EXISTS pg_major_version INTEGER"
                )),
                timeout=5.0,
            )
            await conn.commit()
        print("[startup] Миграция pg_major_version: OK")
    except asyncio.TimeoutError:
        print("[startup] Миграция pg_major_version: таймаут")
    except Exception as e:
        print(f"[startup] Миграция pg_major_version: {e}")


async def _migrate_structure_sync_target_server() -> None:
    """Колонка target_server_id для миграции структуры (сервер-приёмник).
    Старым сценариям = prod_server_id (поведение in-place не меняется)."""
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(conn.execute(text(
                "ALTER TABLE structure_sync_scenarios "
                "ADD COLUMN IF NOT EXISTS target_server_id INTEGER"
            )), timeout=5.0)
            await asyncio.wait_for(conn.execute(text(
                "UPDATE structure_sync_scenarios SET target_server_id = prod_server_id "
                "WHERE target_server_id IS NULL"
            )), timeout=5.0)
            await conn.commit()
        print("[startup] Миграция structure_sync.target_server_id: OK")
    except asyncio.TimeoutError:
        print("[startup] Миграция target_server_id: таймаут")
    except Exception as e:
        print(f"[startup] Миграция target_server_id: {e}")


async def _migrate_scenario_reuse_dump() -> None:
    """Колонки для переиспользуемого дампа сценария (reuse_dump_*)."""
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            await asyncio.wait_for(
                conn.execute(text(
                    "ALTER TABLE restore_scenarios "
                    "ADD COLUMN IF NOT EXISTS reuse_dump_path TEXT, "
                    "ADD COLUMN IF NOT EXISTS reuse_dump_size INTEGER, "
                    "ADD COLUMN IF NOT EXISTS reuse_dump_at TIMESTAMP"
                )),
                timeout=5.0,
            )
            await conn.commit()
        print("[startup] Миграция reuse_dump_*: OK")
    except asyncio.TimeoutError:
        print("[startup] Миграция reuse_dump_*: таймаут")
    except Exception as e:
        print(f"[startup] Миграция reuse_dump_*: {e}")


async def _seed_cron_schedules() -> int:
    from app.models.cron_schedule import CronSchedule, DEFAULT_SCHEDULES
    from sqlalchemy import select, func
    async with AsyncSessionLocal() as session:
        count_result = await session.execute(select(func.count()).select_from(CronSchedule))
        if count_result.scalar() > 0:
            return 0
        for name, expr, desc in DEFAULT_SCHEDULES:
            session.add(CronSchedule(name=name, cron_expression=expr, description=desc, is_builtin=True))
        await session.commit()
    return len(DEFAULT_SCHEDULES)


def _celery_active_ids():
    """set task_id, реально выполняемых воркерами; None — воркеры не ответили."""
    try:
        from app.tasks.celery_app import celery
        replies = celery.control.inspect(timeout=5).active()
    except Exception:  # noqa: BLE001
        return None
    if not replies:
        return None
    ids = set()
    for _w, tasks in replies.items():
        for t in (tasks or []):
            if t.get("id"):
                ids.add(t["id"])
    return ids


async def _cleanup_stale_running_backups() -> int:
    """Гасит только running-бэкапы, чьей задачи НЕТ среди активных в Celery.

    Раньше слепой сброс ВСЕХ running при старте backend бил живые бэкапы, идущие
    в отдельном контейнере worker (backend пересобирается часто). Если воркер не
    ответил (не поднят) — ничего не трогаем: его задачи живы, осиротевшие подчистит
    worker_ready-хендлер самого воркера."""
    from app.models.backup import BackupHistory, RestoreHistory
    from sqlalchemy import select as _select

    active = _celery_active_ids()
    if active is None:
        return 0
    async with AsyncSessionLocal() as session:
        reset = 0
        rows = (await session.execute(
            _select(BackupHistory).where(BackupHistory.status == "running")
        )).scalars().all()
        for b in rows:
            if b.task_id and b.task_id in active:
                continue  # задача жива — не трогаем
            b.status = "failed"
            b.stage = "aborted"
            b.error_message = "Задача прервана (нет активной задачи Celery)"
            b.finished_at = datetime.utcnow()
            reset += 1
        rrows = (await session.execute(
            _select(RestoreHistory).where(RestoreHistory.status == "running")
        )).scalars().all()
        for rr in rrows:
            if rr.task_id and rr.task_id in active:
                continue
            rr.status = "failed"
            rr.error_message = "Задача прервана (нет активной задачи Celery)"
            rr.finished_at = datetime.utcnow()
            reset += 1
        await session.commit()
    return reset


async def _migrate_multi_tenant() -> None:
    """owner_id на сущностях + перенос существующих данных первому пользователю."""
    import asyncio
    from sqlalchemy import text
    statements = [
        "ALTER TABLE servers ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "UPDATE servers SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_servers_owner_id ON servers(owner_id)",
        "ALTER TABLE servers DROP CONSTRAINT IF EXISTS servers_name_key",
        "ALTER TABLE servers DROP CONSTRAINT IF EXISTS uq_servers_owner_name",
        "ALTER TABLE servers ADD CONSTRAINT uq_servers_owner_name UNIQUE (owner_id, name)",
        "ALTER TABLE restore_scenarios ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "UPDATE restore_scenarios SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_restore_scenarios_owner_id ON restore_scenarios(owner_id)",
        "ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "UPDATE notification_channels SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_notification_channels_owner_id ON notification_channels(owner_id)",
        "ALTER TABLE notification_channels DROP CONSTRAINT IF EXISTS notification_channels_name_key",
        "ALTER TABLE notification_channels DROP CONSTRAINT IF EXISTS uq_notification_channels_owner_name",
        "ALTER TABLE notification_channels ADD CONSTRAINT uq_notification_channels_owner_name UNIQUE (owner_id, name)",
        "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "UPDATE alert_rules SET owner_id = (SELECT id FROM users ORDER BY id LIMIT 1) WHERE owner_id IS NULL",
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_owner_id ON alert_rules(owner_id)",
        "ALTER TABLE cron_schedules ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE",
        "CREATE INDEX IF NOT EXISTS ix_cron_schedules_owner_id ON cron_schedules(owner_id)",
    ]
    try:
        async with engine.connect() as conn:
            for sql in statements:
                await asyncio.wait_for(conn.execute(text(sql)), timeout=10.0)
            await conn.commit()
        print("[startup] Миграция multi-tenant owner_id: OK")
    except asyncio.TimeoutError:
        print("[startup] Миграция multi-tenant: таймаут")
    except Exception as e:
        print(f"[startup] Миграция multi-tenant: {e}")


async def _migrate_organizations() -> None:
    """Организации + organization_id на сущностях + ACL."""
    import asyncio
    from sqlalchemy import text
    statements = [
        """CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS organization_members (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            org_role VARCHAR(50) NOT NULL DEFAULT 'viewer',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_org_members_org_user UNIQUE (organization_id, user_id)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_organization_members_organization_id ON organization_members(organization_id)",
        "CREATE INDEX IF NOT EXISTS ix_organization_members_user_id ON organization_members(user_id)",
        "DROP TABLE IF EXISTS role_database_access",
        "DROP TABLE IF EXISTS role_server_access",
        """CREATE TABLE IF NOT EXISTS member_server_access (
            id SERIAL PRIMARY KEY,
            member_id INTEGER NOT NULL REFERENCES organization_members(id) ON DELETE CASCADE,
            server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
            CONSTRAINT uq_member_server_access UNIQUE (member_id, server_id)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_member_server_access_member_id ON member_server_access(member_id)",
        "CREATE INDEX IF NOT EXISTS ix_member_server_access_server_id ON member_server_access(server_id)",
        """CREATE TABLE IF NOT EXISTS member_database_access (
            id SERIAL PRIMARY KEY,
            member_id INTEGER NOT NULL REFERENCES organization_members(id) ON DELETE CASCADE,
            server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
            database_name VARCHAR(255) NOT NULL,
            CONSTRAINT uq_member_database_access UNIQUE (member_id, server_id, database_name)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_member_database_access_member_id ON member_database_access(member_id)",
        "CREATE INDEX IF NOT EXISTS ix_member_database_access_server_id ON member_database_access(server_id)",
        "ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
        "CREATE INDEX IF NOT EXISTS ix_audit_log_organization_id ON audit_log(organization_id)",
        "ALTER TABLE servers ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE",
        "ALTER TABLE restore_scenarios ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE",
        "ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE",
        "ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE",
        "ALTER TABLE cron_schedules ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE",
        """UPDATE servers s SET organization_id = om.organization_id
           FROM organization_members om
           WHERE s.owner_id = om.user_id AND s.organization_id IS NULL""",
        """UPDATE restore_scenarios t SET organization_id = om.organization_id
           FROM organization_members om
           WHERE t.owner_id = om.user_id AND t.organization_id IS NULL""",
        """UPDATE notification_channels t SET organization_id = om.organization_id
           FROM organization_members om
           WHERE t.owner_id = om.user_id AND t.organization_id IS NULL""",
        """UPDATE alert_rules t SET organization_id = om.organization_id
           FROM organization_members om
           WHERE t.owner_id = om.user_id AND t.organization_id IS NULL""",
        """UPDATE cron_schedules t SET organization_id = om.organization_id
           FROM organization_members om
           WHERE t.owner_id = om.user_id AND t.organization_id IS NULL AND t.is_builtin = FALSE""",
        "UPDATE users SET role = 'user' WHERE role = 'owner'",
        "ALTER TABLE servers DROP CONSTRAINT IF EXISTS uq_servers_owner_name",
        "ALTER TABLE servers DROP CONSTRAINT IF EXISTS uq_servers_org_name",
        "ALTER TABLE servers ADD CONSTRAINT uq_servers_org_name UNIQUE (organization_id, name)",
        "ALTER TABLE notification_channels DROP CONSTRAINT IF EXISTS uq_notification_channels_owner_name",
        "ALTER TABLE notification_channels DROP CONSTRAINT IF EXISTS uq_notification_channels_org_name",
        "ALTER TABLE notification_channels ADD CONSTRAINT uq_notification_channels_org_name UNIQUE (organization_id, name)",
        "CREATE INDEX IF NOT EXISTS ix_servers_organization_id ON servers(organization_id)",
        "CREATE INDEX IF NOT EXISTS ix_restore_scenarios_organization_id ON restore_scenarios(organization_id)",
        "CREATE INDEX IF NOT EXISTS ix_notification_channels_organization_id ON notification_channels(organization_id)",
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_organization_id ON alert_rules(organization_id)",
        "CREATE INDEX IF NOT EXISTS ix_cron_schedules_organization_id ON cron_schedules(organization_id)",
    ]
    try:
        async with engine.connect() as conn:
            for sql in statements:
                await asyncio.wait_for(conn.execute(text(sql)), timeout=15.0)
            await conn.commit()
        print("[startup] Миграция organizations: OK")
    except asyncio.TimeoutError:
        print("[startup] Миграция organizations: таймаут")
    except Exception as e:
        print(f"[startup] Миграция organizations: {e}")


async def _seed_super_admin() -> None:
    """Создаёт супер-админа platform (role=admin) если его ещё нет."""
    from sqlalchemy import select
    from app.models.user import User
    from app.services.auth_service import hash_password
    from app.config import settings

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == settings.super_admin_username)
        )
        if result.scalar_one_or_none():
            return
        user = User(
            username=settings.super_admin_username,
            email=settings.super_admin_email,
            password_hash=hash_password(settings.super_admin_password),
            role="admin",
        )
        session.add(user)
        await session.commit()
    print(f"[startup] Супер-админ '{settings.super_admin_username}' создан")


def _sync_org_queues_startup() -> dict[str, list[str]]:
    from app.tasks.queues import sync_org_queues_with_db
    return sync_org_queues_with_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_excluded_tables()
    await _migrate_pg_major_version()
    await _migrate_scenario_reuse_dump()
    await _migrate_structure_sync_target_server()
    await _migrate_multi_tenant()
    await _migrate_organizations()
    await _seed_super_admin()
    cleaned = await _cleanup_stale_running_backups()
    if cleaned:
        print(f"[startup] Помечено как failed: {cleaned} зависших бэкапов")
    queue_sync = await asyncio.to_thread(_sync_org_queues_startup)
    if queue_sync.get("removed"):
        print(f"[startup] RabbitMQ: удалены очереди {queue_sync['removed']}")
    seeded = await _seed_cron_schedules()
    if seeded:
        print(f"[startup] Добавлено {seeded} базовых расписаний")

    # Публикатор статуса worker в WS (заменяет клиентский HTTP-поллинг health/queue).
    from app.services.worker_status_service import worker_status_publisher
    status_task = asyncio.create_task(worker_status_publisher())
    print("[startup] Публикатор статуса worker запущен")
    try:
        yield
    finally:
        status_task.cancel()
        try:
            await status_task
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(title="PG Admin System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Любое непойманное исключение эндпоинта → 500 с ВНЯТНОЙ причиной + лог.
    (HTTPException обрабатывается отдельным дефолтным хендлером и сюда не попадает.)"""
    tb = traceback.format_exc()
    print(f"[api] Необработанное исключение {request.method} {request.url.path}: "
          f"{type(exc).__name__}: {exc}\n{tb}", flush=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Внутренняя ошибка: {type(exc).__name__}: {exc}"},
    )


app.include_router(auth.router, prefix="/api")
app.include_router(organizations.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(audit.router, prefix="/api")
app.include_router(servers.router, prefix="/api")
app.include_router(s3_storages.router, prefix="/api")
app.include_router(servers.pg_versions_router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(databases.router, prefix="/api")
app.include_router(backups.router, prefix="/api")
app.include_router(monitoring.router, prefix="/api")
app.include_router(diagnostics.router, prefix="/api")
app.include_router(pg_config.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(scenarios.router, prefix="/api")
app.include_router(structure_sync.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(cron_schedules.router, prefix="/api")
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    from app.tasks.celery_app import celery
    import asyncio

    def _ping_workers():
        try:
            inspector = celery.control.inspect(timeout=5)
            pong = inspector.ping()
            # pong — dict {worker_name: [{'ok': 'pong'}]}, None при таймауте
            return isinstance(pong, dict) and len(pong) > 0
        except Exception:
            return False

    worker_alive = await asyncio.get_event_loop().run_in_executor(None, _ping_workers)
    return {
        "status": "ok",
        "worker": "online" if worker_alive else "offline",
    }
