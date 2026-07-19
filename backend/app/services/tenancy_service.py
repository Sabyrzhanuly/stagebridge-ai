from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.server import Server
from app.models.user import User
from app.models.organization import OrganizationMember, MemberServerAccess, MemberDatabaseAccess
from app.services.auth_service import (
    is_platform_admin,
    has_org_permission,
    ORG_ROLES_WITH_ALL_SERVERS,
)


@dataclass
class OrgContext:
    organization_id: int
    org_role: str
    member: OrganizationMember | None = None
    impersonated: bool = False


def is_global_admin(user: User) -> bool:
    return is_platform_admin(user.role)


async def resolve_org_context(
    user: User,
    db: AsyncSession,
    org_id: int | None,
    member_id: int | None,
) -> OrgContext | None:
    if is_global_admin(user):
        return None
    if member_id is None or org_id is None:
        raise HTTPException(403, "Не выбрана организация")
    member = await db.get(OrganizationMember, member_id)
    if not member or not member.is_active or member.user_id != user.id:
        raise HTTPException(403, "Нет доступа к организации")
    if member.organization_id != org_id:
        raise HTTPException(403, "Нет доступа к организации")
    return OrgContext(
        member=member,
        organization_id=member.organization_id,
        org_role=member.org_role,
        impersonated=False,
    )


async def get_primary_membership(user: User, db: AsyncSession) -> OrganizationMember | None:
    result = await db.execute(
        select(OrganizationMember)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.is_active.is_(True),
        )
        .order_by(OrganizationMember.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


def scope_organization_id(user: User, ctx: OrgContext | None) -> int | None:
    if is_global_admin(user):
        return None
    if ctx is None:
        raise HTTPException(403, "Не выбрана организация")
    return ctx.organization_id


async def member_has_server_access(
    ctx: OrgContext,
    server_id: int,
    db: AsyncSession,
) -> bool:
    if ctx.org_role in ORG_ROLES_WITH_ALL_SERVERS:
        return True
    if ctx.member is None:
        return False
    result = await db.execute(
        select(MemberServerAccess.id)
        .where(
            MemberServerAccess.member_id == ctx.member.id,
            MemberServerAccess.server_id == server_id,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def filter_database_names(
    ctx: OrgContext,
    server_id: int,
    database_names: list[str],
    db: AsyncSession,
) -> list[str]:
    if ctx.org_role in ORG_ROLES_WITH_ALL_SERVERS:
        return database_names
    if ctx.member is None:
        return []
    result = await db.execute(
        select(MemberDatabaseAccess.database_name)
        .where(
            MemberDatabaseAccess.member_id == ctx.member.id,
            MemberDatabaseAccess.server_id == server_id,
        )
    )
    allowed = [row[0] for row in result.all()]
    if not allowed:
        return database_names
    allowed_set = set(allowed)
    return [name for name in database_names if name in allowed_set]


async def ensure_database_access(
    ctx: OrgContext,
    server_id: int,
    database_name: str,
    db: AsyncSession,
) -> None:
    filtered = await filter_database_names(ctx, server_id, [database_name], db)
    if database_name not in filtered:
        raise HTTPException(403, f"Нет доступа к базе {database_name}")


async def get_accessible_server(
    server_id: int,
    user: User,
    ctx: OrgContext | None,
    db: AsyncSession,
    *,
    permission: str | None = None,
) -> Server:
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    if is_global_admin(user):
        return server
    if ctx is None:
        raise HTTPException(403, "Не выбрана организация")
    if server.organization_id != ctx.organization_id:
        raise HTTPException(403, "Нет доступа к этому серверу")
    if permission and not has_org_permission(ctx.org_role, permission):
        raise HTTPException(403, f"Нет права: {permission}")
    if not await member_has_server_access(ctx, server_id, db):
        raise HTTPException(403, "Нет доступа к этому серверу")
    return server


def servers_stmt(user: User, ctx: OrgContext | None):
    stmt = select(Server)
    org_id = scope_organization_id(user, ctx)
    if org_id is not None:
        stmt = stmt.where(Server.organization_id == org_id)
    return stmt


async def accessible_server_ids(
    user: User,
    ctx: OrgContext | None,
    db: AsyncSession,
) -> list[int] | None:
    if is_global_admin(user):
        return None
    if ctx is None:
        return []
    if ctx.org_role in ORG_ROLES_WITH_ALL_SERVERS:
        result = await db.execute(
            select(Server.id).where(Server.organization_id == ctx.organization_id)
        )
        return [row[0] for row in result.all()]
    if ctx.member is None:
        return []
    result = await db.execute(
        select(MemberServerAccess.server_id)
        .join(Server, Server.id == MemberServerAccess.server_id)
        .where(
            MemberServerAccess.member_id == ctx.member.id,
            Server.organization_id == ctx.organization_id,
        )
    )
    return [row[0] for row in result.all()]


def apply_org_filter(stmt, user: User, ctx: OrgContext | None, org_column):
    org_id = scope_organization_id(user, ctx)
    if org_id is not None:
        stmt = stmt.where(org_column == org_id)
    return stmt


async def servers_stmt_for_member(
    user: User,
    ctx: OrgContext | None,
    db: AsyncSession,
):
    stmt = servers_stmt(user, ctx)
    if ctx is None or ctx.org_role in ORG_ROLES_WITH_ALL_SERVERS:
        return stmt
    ids = await accessible_server_ids(user, ctx, db)
    if not ids:
        return stmt.where(Server.id == -1)
    return stmt.where(Server.id.in_(ids))


# backward-compatible aliases used during refactor
get_owned_server = get_accessible_server
apply_owner_filter = apply_org_filter
owned_server_ids = accessible_server_ids
role_has_server_access = member_has_server_access
