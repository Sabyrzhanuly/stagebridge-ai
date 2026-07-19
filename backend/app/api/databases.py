from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.server import Server
from app.models.user import User
from app.schemas.database import DatabaseOut, DatabaseCreate, SchemaOut, TableOut, EventTriggerOut
from app.services import database_service
from app.services.audit_service import audit_action
from app.services.tenancy_service import get_owned_server, filter_database_names, ensure_database_access
from app.api.deps import get_auth_context, RequirePermission, AuthContext

router = APIRouter(
    prefix="/servers/{server_id}/databases",
    tags=["databases"],
    dependencies=[Depends(get_auth_context)],
)


async def _get_server(server_id: int, auth: AuthContext, db: AsyncSession) -> Server:
    return await get_owned_server(server_id, auth.user, auth.org, db)


async def _ensure_db_access(auth: AuthContext, server_id: int, db_name: str, db: AsyncSession) -> None:
    if auth.org is not None:
        await ensure_database_access(auth.org, server_id, db_name, db)


@router.get("", response_model=list[DatabaseOut])
async def list_databases(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await _get_server(server_id, auth, db)
    databases = await database_service.list_databases(server)
    if auth.org is not None:
        names = [d["datname"] for d in databases]
        allowed = await filter_database_names(auth.org, server_id, names, db)
        allowed_set = set(allowed)
        databases = [d for d in databases if d["datname"] in allowed_set]
    return databases


@router.post("", status_code=201)
async def create_database(
    server_id: int,
    data: DatabaseCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_servers")),
):
    server = await _get_server(server_id, auth, db)
    await database_service.create_database(server, data.name, data.mode, data.with_service)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="database",
        entity_id=data.name,
        payload={"server_id": server_id, "mode": data.mode, "with_service": data.with_service},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"status": "ok", "database": data.name}


@router.delete("/{db_name}", status_code=204)
async def drop_database(
    server_id: int,
    db_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("dangerous_ops")),
):
    server = await _get_server(server_id, auth, db)
    await _ensure_db_access(auth, server_id, db_name, db)
    if server.environment == "production":
        raise HTTPException(403, "Удаление БД на production запрещено")
    await database_service.drop_database(server, db_name)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="database",
        entity_id=db_name,
        payload={"server_id": server_id},
        organization_id=auth.org.organization_id if auth.org else None,
    )


@router.get("/{db_name}/schemas", response_model=list[SchemaOut])
async def list_schemas(
    server_id: int,
    db_name: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await _get_server(server_id, auth, db)
    await _ensure_db_access(auth, server_id, db_name, db)
    return await database_service.list_schemas(server, db_name)


@router.get("/{db_name}/tables", response_model=list[TableOut])
async def list_tables(
    server_id: int,
    db_name: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await _get_server(server_id, auth, db)
    await _ensure_db_access(auth, server_id, db_name, db)
    return await database_service.list_tables(server, db_name)


@router.get("/{db_name}/event-triggers", response_model=list[EventTriggerOut])
async def list_event_triggers(
    server_id: int,
    db_name: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await _get_server(server_id, auth, db)
    await _ensure_db_access(auth, server_id, db_name, db)
    return await database_service.list_event_triggers(server, db_name)


@router.get("/{db_name}/tables-size")
async def list_tables_size(
    server_id: int,
    db_name: str,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await _get_server(server_id, auth, db)
    await _ensure_db_access(auth, server_id, db_name, db)
    return await database_service.list_tables_size(server, db_name)
