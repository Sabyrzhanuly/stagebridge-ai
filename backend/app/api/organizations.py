from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.organization import (
    Organization,
    OrganizationMember,
    MemberServerAccess,
    MemberDatabaseAccess,
    slugify,
)
from app.models.server import Server
from app.schemas.organization import (
    OrganizationOut,
    MemberOut,
    MemberCreate,
    MemberUpdate,
    MemberAccessOut,
    MemberAccessUpdate,
    OrgRolesCatalogOut,
)
from app.services.auth_service import (
    hash_password,
    password_policy_error,
    ORG_ROLE_PERMISSIONS,
    ORG_ROLES_WITH_ALL_SERVERS,
    verify_password,
    org_roles_catalog,
)
from app.services.audit_service import audit_action
from app.services.tenancy_service import OrgContext, is_global_admin
from app.api.deps import get_auth_context, get_org_context, RequirePermission, AuthContext

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _valid_org_roles() -> set[str]:
    return set(ORG_ROLE_PERMISSIONS.keys())


def _role_all_servers(org_role: str) -> bool:
    return org_role in ORG_ROLES_WITH_ALL_SERVERS


async def _member_server_ids(member_id: int, db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(MemberServerAccess.server_id)
        .where(MemberServerAccess.member_id == member_id)
    )
    return [row[0] for row in result.all()]


async def _member_access_out(
    member: OrganizationMember,
    db: AsyncSession,
) -> MemberAccessOut:
    if _role_all_servers(member.org_role):
        return MemberAccessOut(all_servers=True, server_ids=[], databases=[])
    server_ids = await _member_server_ids(member.id, db)
    db_result = await db.execute(
        select(MemberDatabaseAccess.server_id, MemberDatabaseAccess.database_name)
        .where(MemberDatabaseAccess.member_id == member.id)
    )
    databases = [
        {"server_id": row[0], "database_name": row[1]}
        for row in db_result.all()
    ]
    return MemberAccessOut(all_servers=False, server_ids=server_ids, databases=databases)


async def _validate_member_access_payload(
    organization_id: int,
    data: MemberAccessUpdate,
    db: AsyncSession,
) -> set[int]:
    org_servers = await db.execute(
        select(Server.id).where(Server.organization_id == organization_id)
    )
    org_server_ids = {row[0] for row in org_servers.all()}
    for sid in data.server_ids:
        if sid not in org_server_ids:
            raise HTTPException(400, f"Сервер {sid} не принадлежит организации")
    for item in data.databases:
        sid = int(item.get("server_id", 0))
        name = str(item.get("database_name", "")).strip()
        if sid not in org_server_ids or not name:
            raise HTTPException(400, "Неверная запись доступа к базе")
        if sid not in data.server_ids:
            raise HTTPException(400, "База указана для сервера, не входящего в список доступа")
    return org_server_ids


async def _member_out(member: OrganizationMember, db: AsyncSession) -> MemberOut:
    user = await db.get(User, member.user_id)
    all_servers = _role_all_servers(member.org_role)
    server_ids = [] if all_servers else await _member_server_ids(member.id, db)
    return MemberOut(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        username=user.username if user else "",
        email=user.email if user else "",
        org_role=member.org_role,
        is_active=member.is_active,
        created_at=member.created_at,
        all_servers=all_servers,
        server_ids=server_ids,
    )


@router.get("/me", response_model=OrganizationOut)
async def get_my_organization(
    ctx: OrgContext = Depends(get_org_context),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, ctx.organization_id)
    if not org:
        raise HTTPException(404, "Организация не найдена")
    return org


@router.get("/org-roles", response_model=OrgRolesCatalogOut)
async def list_org_roles(
    _: AuthContext = Depends(get_auth_context),
    __: OrgContext = Depends(get_org_context),
):
    return org_roles_catalog()


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    auth: AuthContext = Depends(get_auth_context),
    ctx: OrgContext = Depends(get_org_context),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("manage_members")),
):
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == ctx.organization_id)
        .order_by(OrganizationMember.id)
    )
    members = result.scalars().all()
    return [await _member_out(m, db) for m in members]


@router.post("/members", response_model=MemberOut, status_code=201)
async def create_member(
    data: MemberCreate,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    ctx: OrgContext = Depends(get_org_context),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("manage_members")),
):
    if data.org_role not in _valid_org_roles():
        raise HTTPException(400, f"Роль должна быть одной из: {', '.join(sorted(_valid_org_roles()))}")
    if err := password_policy_error(data.password):
        raise HTTPException(400, err)

    exists = await db.execute(
        select(User).where(
            (User.username == data.username.strip()) | (User.email == data.email.strip().lower())
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(409, "Пользователь с таким логином или email уже существует")

    user = User(
        username=data.username.strip(),
        email=data.email.strip().lower(),
        password_hash=hash_password(data.password),
        role="user",
    )
    db.add(user)
    await db.flush()

    member = OrganizationMember(
        organization_id=ctx.organization_id,
        user_id=user.id,
        org_role=data.org_role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="organization_member",
        entity_id=member.id,
        payload={"username": user.username, "org_role": data.org_role},
        organization_id=ctx.organization_id,
    )
    return await _member_out(member, db)


@router.patch("/members/{member_id}", response_model=MemberOut)
async def update_member(
    member_id: int,
    data: MemberUpdate,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    ctx: OrgContext = Depends(get_org_context),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("manage_members")),
):
    member = await db.get(OrganizationMember, member_id)
    if not member or member.organization_id != ctx.organization_id:
        raise HTTPException(404, "Участник не найден")
    if not is_global_admin(auth.user) and ctx.member is not None and member.id == ctx.member.id and data.is_active is False:
        raise HTTPException(400, "Нельзя деактивировать себя")

    if data.org_role is not None:
        if data.org_role not in _valid_org_roles():
            raise HTTPException(400, "Неверная роль")
        member.org_role = data.org_role
    if data.is_active is not None:
        member.is_active = data.is_active
    if data.password:
        if err := password_policy_error(data.password):
            raise HTTPException(400, err)
        user = await db.get(User, member.user_id)
        if user:
            user.password_hash = hash_password(data.password)

    await db.commit()
    await db.refresh(member)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="organization_member",
        entity_id=member.id,
        payload=data.model_dump(exclude_unset=True),
        organization_id=ctx.organization_id,
    )
    return await _member_out(member, db)


async def _get_org_member(member_id: int, ctx: OrgContext, db: AsyncSession) -> OrganizationMember:
    member = await db.get(OrganizationMember, member_id)
    if not member or member.organization_id != ctx.organization_id:
        raise HTTPException(404, "Участник не найден")
    return member


@router.get("/members/{member_id}/access", response_model=MemberAccessOut)
async def get_member_access(
    member_id: int,
    ctx: OrgContext = Depends(get_org_context),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("manage_members")),
):
    member = await _get_org_member(member_id, ctx, db)
    return await _member_access_out(member, db)


@router.put("/members/{member_id}/access", response_model=MemberAccessOut)
async def update_member_access(
    member_id: int,
    data: MemberAccessUpdate,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    ctx: OrgContext = Depends(get_org_context),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("manage_members")),
):
    member = await _get_org_member(member_id, ctx, db)
    if _role_all_servers(member.org_role):
        raise HTTPException(400, "У Администратора доступ ко всем серверам — настройка не требуется")

    await _validate_member_access_payload(ctx.organization_id, data, db)

    await db.execute(
        MemberServerAccess.__table__.delete().where(
            MemberServerAccess.member_id == member.id,
        )
    )
    await db.execute(
        MemberDatabaseAccess.__table__.delete().where(
            MemberDatabaseAccess.member_id == member.id,
        )
    )

    for sid in data.server_ids:
        db.add(MemberServerAccess(member_id=member.id, server_id=sid))
    for item in data.databases:
        db.add(MemberDatabaseAccess(
            member_id=member.id,
            server_id=int(item["server_id"]),
            database_name=str(item["database_name"]).strip(),
        ))

    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="member_access",
        entity_id=member.id,
        payload={"server_ids": data.server_ids, "databases_count": len(data.databases)},
        organization_id=ctx.organization_id,
    )
    return await _member_access_out(member, db)
