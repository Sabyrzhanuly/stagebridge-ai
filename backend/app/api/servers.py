import asyncio

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.server import Server
from app.models.organization import Organization
from app.models.minio_config import MinioConfig
from app.models.user import User
from app.schemas.server import ServerCreate, ServerUpdate, ServerOut, ServerTestResult, ServerOrganizationAssign
from app.schemas.s3_storage import ServerStorageAssign
from app.services.crypto import encrypt, decrypt
from app.services.pg_connection import test_connection
from app.services.pg_error_hints import classify_pg_error
from app.services.server_health_service import apply_health_probe, DEFAULT_OFFLINE_THRESHOLD
from app.services import minio_service, pg_client_service
from app.services import pg_client_catalog_service
from app.tasks.pg_client_tasks import (
    install_pg_client_task,
    refresh_pg_repo_task,
    uninstall_pg_client_task,
)
from app.tasks.queues import enqueue_platform_task, register_org_queue
from app.services.audit_service import audit_action
from app.services.tenancy_service import get_owned_server, servers_stmt_for_member, is_global_admin
from app.api.deps import get_auth_context, RequirePermission, AuthContext, require_platform_admin


def _server_out(
    server: Server,
    storage_name: str | None = None,
    organization_name: str | None = None,
) -> ServerOut:
    hint = classify_pg_error(server.health_error) if server.health_error else None
    return ServerOut(
        id=server.id,
        name=server.name,
        host=server.host,
        port=server.port,
        admin_user=server.admin_user,
        ssh_user=server.ssh_user,
        environment=server.environment,
        is_active=server.is_active,
        pg_major_version=server.pg_major_version,
        organization_id=server.organization_id,
        organization_name=organization_name,
        storage_id=server.storage_id,
        storage_name=storage_name,
        health_status=server.health_status or "unknown",
        health_error=server.health_error,
        health_error_code=hint.code if hint else None,
        health_error_title=hint.title if server.health_error else None,
        health_error_hint=hint.hint if server.health_error else None,
        health_fail_count=server.health_fail_count or 0,
        health_checked_at=server.health_checked_at,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


async def _organization_names(db: AsyncSession, org_ids: set[int]) -> dict[int, str]:
    if not org_ids:
        return {}
    result = await db.execute(
        select(Organization.id, Organization.name).where(Organization.id.in_(org_ids))
    )
    return {row.id: row.name for row in result.all()}


async def _server_out_enriched(db: AsyncSession, server: Server) -> ServerOut:
    storage_name = None
    if server.storage_id:
        storage = await db.get(MinioConfig, server.storage_id)
        storage_name = storage.name if storage else None
    org_name = None
    if server.organization_id:
        org = await db.get(Organization, server.organization_id)
        org_name = org.name if org else None
    return _server_out(server, storage_name, org_name)


async def _storage_names(db: AsyncSession, storage_ids: set[int]) -> dict[int, str]:
    if not storage_ids:
        return {}
    result = await db.execute(
        select(MinioConfig.id, MinioConfig.name).where(MinioConfig.id.in_(storage_ids))
    )
    return {row.id: row.name for row in result.all()}


router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("", response_model=list[ServerOut])
async def get_servers(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    stmt = await servers_stmt_for_member(auth.user, auth.org, db)
    result = await db.execute(stmt.order_by(Server.name))
    servers = result.scalars().all()
    storage_names = await _storage_names(db, {s.storage_id for s in servers if s.storage_id})
    org_names = await _organization_names(db, {s.organization_id for s in servers if s.organization_id})
    return [
        _server_out(
            s,
            storage_names.get(s.storage_id) if s.storage_id else None,
            org_names.get(s.organization_id) if s.organization_id else None,
        )
        for s in servers
    ]


@router.post("", response_model=ServerOut, status_code=201)
async def create_server(
    data: ServerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_servers")),
):
    if auth.org is None and not is_global_admin(auth.user):
        raise HTTPException(
            403,
            "Выберите организацию (заголовок X-Organization-Id) или войдите как участник org",
        )
    org_id = auth.org.organization_id if auth.org else None
    if is_global_admin(auth.user) and data.organization_id is not None:
        org_id = data.organization_id
    if org_id is None:
        raise HTTPException(403, "Укажите организацию для нового сервера")
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    server = Server(
        organization_id=org_id,
        name=data.name,
        host=data.host,
        port=data.port,
        admin_user=data.admin_user,
        admin_password_encrypted=encrypt(data.admin_password),
        ssh_user=data.ssh_user,
        environment=data.environment,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    register_org_queue(org_id)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="server",
        entity_id=server.id,
        payload={"name": server.name, "host": server.host, "port": server.port},
        organization_id=org_id,
    )
    return await _server_out_enriched(db, server)


@router.get("/{server_id}", response_model=ServerOut)
async def get_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db, permission="view_servers")
    return await _server_out_enriched(db, server)


@router.patch("/{server_id}", response_model=ServerOut)
async def update_server(
    server_id: int,
    data: ServerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_servers")),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db, permission="manage_servers")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "admin_password" and value is not None:
            server.admin_password_encrypted = encrypt(value)
        elif field != "admin_password":
            setattr(server, field, value)
    await db.commit()
    await db.refresh(server)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="server",
        entity_id=server.id,
        payload=data.model_dump(exclude_unset=True),
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return await _server_out_enriched(db, server)


@router.put("/{server_id}/organization", response_model=ServerOut)
async def assign_server_organization(
    server_id: int,
    data: ServerOrganizationAssign,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_servers")),
):
    if not is_global_admin(auth.user):
        raise HTTPException(403, "Назначать организацию может только platform admin")
    server = await get_owned_server(server_id, auth.user, auth.org, db, permission="manage_servers")
    org = await db.get(Organization, data.organization_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    if server.storage_id:
        storage = await db.get(MinioConfig, server.storage_id)
        if storage and storage.organization_id != data.organization_id:
            server.storage_id = None
    server.organization_id = data.organization_id
    await db.commit()
    await db.refresh(server)
    register_org_queue(org.id)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="server",
        entity_id=server.id,
        payload={"organization_id": data.organization_id},
        organization_id=data.organization_id,
    )
    return await _server_out_enriched(db, server)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_servers")),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db, permission="manage_servers")
    server_name = server.name
    await db.delete(server)
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="server",
        entity_id=server_id,
        payload={"name": server_name},
        organization_id=auth.org.organization_id if auth.org else None,
    )


@router.post("/{server_id}/test", response_model=ServerTestResult)
async def test_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db, permission="view_servers")
    try:
        password = decrypt(server.admin_password_encrypted)
    except (InvalidToken, Exception):
        await audit_action(
            db,
            user=auth.user,
            request=request,
            action="execute",
            entity_type="server",
            entity_id=server_id,
            payload={"operation": "test_connection"},
            result="failed",
            organization_id=auth.org.organization_id if auth.org else None,
        )
        return ServerTestResult(
            success=False,
            version=None,
            error="Не удалось расшифровать пароль. Обновите пароль сервера.",
            error_code="auth_failed",
            error_title="Ошибка аутентификации",
            error_hint="Обновите пароль admin_user в карточке сервера.",
        )
    ok, version, error, pg_major = await test_connection(server.host, server.port, server.admin_user, password)
    apply_health_probe(server, ok, error, pg_major, offline_threshold=DEFAULT_OFFLINE_THRESHOLD)
    if ok and pg_major is not None:
        await pg_client_catalog_service.ensure_requested(db, pg_major)
    await db.commit()
    hint = classify_pg_error(error) if error else None
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="server",
        entity_id=server_id,
        payload={"operation": "test_connection", "version": version, "pg_major": pg_major},
        result="success" if ok else "failed",
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return ServerTestResult(
        success=ok,
        version=version,
        error=error,
        error_code=hint.code if hint else None,
        error_title=hint.title if hint else None,
        error_hint=hint.hint if hint else None,
    )


@router.put("/{server_id}/storage", response_model=ServerOut)
async def assign_server_storage(
    server_id: int,
    data: ServerStorageAssign,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    server = await get_owned_server(server_id, auth.user, auth.org, db, permission="run_backup")
    storage_name = None
    if data.storage_id is not None:
        storage = await db.get(MinioConfig, data.storage_id)
        if not storage or storage.organization_id != server.organization_id:
            raise HTTPException(400, "Хранилище не найдено в вашей организации")
        storage_name = storage.name
    server.storage_id = data.storage_id
    await db.commit()
    await db.refresh(server)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="server",
        entity_id=server.id,
        payload={"storage_id": data.storage_id},
        organization_id=server.organization_id,
    )
    return _server_out(server, storage_name)


pg_versions_router = APIRouter(prefix="/pg-client-versions", tags=["servers"])


class PgClientAddRequest(BaseModel):
    major: int
    note: str | None = None


@pg_versions_router.get("/available")
async def get_available_pg_clients(
    refresh: bool = False,
    _: User = Depends(require_platform_admin),
):
    """Список postgresql-client-* из PGDG (apt-cache), без apt-get update."""
    if refresh:
        raise HTTPException(
            400,
            "Для обновления репозитория используйте POST /pg-client-versions/available/refresh",
        )
    result = await asyncio.to_thread(pg_client_service.list_available_clients, refresh=False)
    if not result.get("ok"):
        raise HTTPException(502, result.get("message", "Не удалось получить список пакетов"))
    return result


@pg_versions_router.post("/available/refresh")
async def refresh_available_pg_clients(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
):
    """apt-get update + apt-cache pkgnames — асинхронно с логами в TaskPanel."""
    task = enqueue_platform_task(refresh_pg_repo_task)
    await audit_action(
        db,
        user=user,
        request=request,
        action="refresh",
        entity_type="pg_client_repo",
        entity_id=0,
        payload={"task_id": task.id},
    )
    return {"task_id": task.id, "status": "started"}


@pg_versions_router.get("")
async def get_pg_client_versions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    """Каталог PG-клиентов — только администратор платформы."""
    items = await pg_client_catalog_service.list_catalog_items(db)
    return {"items": items}


@pg_versions_router.post("")
async def add_pg_client_to_catalog(
    data: PgClientAddRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
):
    try:
        row = await pg_client_catalog_service.add_manual(db, data.major, data.note)
    except ValueError as e:
        raise HTTPException(400, str(e))

    await audit_action(
        db,
        user=user,
        request=request,
        action="create",
        entity_type="pg_client",
        entity_id=row.major_version,
        payload={"major": row.major_version, "source": row.source},
    )
    items = await pg_client_catalog_service.list_catalog_items(db)
    item = next((i for i in items if i["major"] == row.major_version), None)
    return item or {"major": row.major_version, "source": row.source}


@pg_versions_router.delete("/{major}/catalog", status_code=204)
async def remove_pg_client_from_catalog(
    major: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
):
    if major < 1:
        raise HTTPException(400, "Некорректная major-версия PostgreSQL")
    try:
        await pg_client_catalog_service.remove_from_catalog(db, major)
    except ValueError as e:
        raise HTTPException(409, str(e))

    await audit_action(
        db,
        user=user,
        request=request,
        action="delete",
        entity_type="pg_client_catalog",
        entity_id=major,
        payload={"major": major},
    )


@pg_versions_router.post("/{major}/install")
async def install_pg_client_version(
    major: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
):
    if major < 1:
        raise HTTPException(400, "Некорректная major-версия PostgreSQL")

    try:
        pg_client_service.validate_installable_major(major)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if pg_client_service.is_installed(major):
        return {
            "task_id": None,
            "status": "already_installed",
            "major": major,
            "message": f"PostgreSQL client {major} уже установлен",
        }

    task = enqueue_platform_task(install_pg_client_task, major)
    await audit_action(
        db,
        user=user,
        request=request,
        action="install",
        entity_type="pg_client",
        entity_id=major,
        payload={"major": major, "task_id": task.id},
    )
    return {"task_id": task.id, "status": "started", "major": major}


@pg_versions_router.delete("/{major}", status_code=200)
async def uninstall_pg_client_version(
    major: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
):
    if major < 1:
        raise HTTPException(400, "Некорректная major-версия PostgreSQL")

    in_use = await db.execute(
        select(Server.id).where(Server.pg_major_version == major).limit(1)
    )
    if in_use.scalar_one_or_none() is not None:
        raise HTTPException(
            409,
            f"Клиент PostgreSQL {major} используется серверами платформы — удаление запрещено",
        )

    if not pg_client_service.is_installed(major):
        return {
            "task_id": None,
            "status": "not_installed",
            "major": major,
            "message": f"PostgreSQL client {major} не установлен",
        }

    task = enqueue_platform_task(uninstall_pg_client_task, major)
    await audit_action(
        db,
        user=user,
        request=request,
        action="delete",
        entity_type="pg_client",
        entity_id=major,
        payload={"major": major, "task_id": task.id},
    )
    return {"task_id": task.id, "status": "started", "major": major}
