from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.server import Server
from app.models.user import User
from app.schemas.role import RoleOut, RoleCreate, ServiceAccountCreate, RoleGrantRevoke
from app.services import role_service
from app.services.audit_service import audit_action
from app.services.tenancy_service import get_owned_server
from app.api.deps import get_auth_context, RequirePermission, AuthContext

router = APIRouter(
    prefix="/servers/{server_id}/roles",
    tags=["roles"],
    dependencies=[Depends(get_auth_context)],
)


async def _get_server(server_id: int, auth: AuthContext, db: AsyncSession) -> Server:
    return await get_owned_server(server_id, auth.user, auth.org, db)


@router.get("", response_model=list[RoleOut])
async def list_roles(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server = await _get_server(server_id, auth, db)
    rows = await role_service.list_roles(server)
    return [
        RoleOut(
            rolname=r["rolname"],
            rolcanlogin=r["rolcanlogin"],
            rolsuper=r["rolsuper"],
            rolinherit=r["rolinherit"],
            rolcreatedb=r["rolcreatedb"],
            rolcreaterole=r["rolcreaterole"],
            rolconnlimit=r["rolconnlimit"],
            member_of=list(r.get("member_of") or []),
        )
        for r in rows
    ]


@router.post("/user", status_code=201)
async def create_user(
    server_id: int,
    data: RoleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_roles")),
):
    server = await _get_server(server_id, auth, db)
    password = await role_service.create_user(server, data.username, data.password, data.group)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="role",
        payload={"server_id": server_id, "username": data.username, "group": data.group},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"username": data.username, "password": password, "group": data.group}


@router.post("/service-account", status_code=201)
async def create_service_account(
    server_id: int,
    data: ServiceAccountCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_roles")),
):
    server = await _get_server(server_id, auth, db)
    password = await role_service.create_service_account(server, data.username, data.password, data.database)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="role",
        payload={"server_id": server_id, "username": data.username, "database": data.database, "kind": "service_account"},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"username": data.username, "password": password, "database": data.database}


@router.post("/{role_name}/grant")
async def grant_role(
    server_id: int,
    role_name: str,
    data: RoleGrantRevoke,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_roles")),
):
    server = await _get_server(server_id, auth, db)
    await role_service.grant_role(server, role_name, data.group)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="role",
        entity_id=role_name,
        payload={"server_id": server_id, "operation": "grant", "group": data.group},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"status": "ok"}


@router.post("/{role_name}/revoke")
async def revoke_role(
    server_id: int,
    role_name: str,
    data: RoleGrantRevoke,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_roles")),
):
    server = await _get_server(server_id, auth, db)
    await role_service.revoke_role(server, role_name, data.group)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="role",
        entity_id=role_name,
        payload={"server_id": server_id, "operation": "revoke", "group": data.group},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"status": "ok"}


@router.delete("/{role_name}", status_code=204)
async def drop_role(
    server_id: int,
    role_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_roles")),
):
    server = await _get_server(server_id, auth, db)
    await role_service.drop_role(server, role_name)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="role",
        entity_id=role_name,
        payload={"server_id": server_id},
        organization_id=auth.org.organization_id if auth.org else None,
    )
