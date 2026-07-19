from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.services.auth_service import decode_token, has_permission, is_platform_admin
from app.services.tenancy_service import OrgContext, resolve_org_context, get_primary_membership


@dataclass
class AuthContext:
    user: User
    org: OrgContext | None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Не авторизован")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(401, "Неверный тип токена")
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Невалидный токен")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Пользователь не найден или деактивирован")
    return user


async def _super_admin_org_context(
    request: Request,
    db: AsyncSession,
) -> OrgContext | None:
    org_hdr = request.headers.get("X-Organization-Id")
    if not org_hdr:
        return None
    try:
        org_id = int(org_hdr)
    except ValueError:
        raise HTTPException(400, "Неверный X-Organization-Id")
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(400, "Организация не найдена")
    return OrgContext(
        organization_id=org.id,
        org_role="org_admin",
        member=None,
        impersonated=True,
    )


async def get_auth_context(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if is_platform_admin(user.role):
        org_ctx = await _super_admin_org_context(request, db)
        return AuthContext(user=user, org=org_ctx)

    org_id = None
    member_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            payload = decode_token(auth_header.split(" ", 1)[1])
            org_id = payload.get("org_id")
            member_id = payload.get("member_id")
            if org_id is not None:
                org_id = int(org_id)
            if member_id is not None:
                member_id = int(member_id)
        except Exception:
            pass

    ctx = await resolve_org_context(user, db, org_id, member_id)
    return AuthContext(user=user, org=ctx)


async def get_org_context(
    auth: AuthContext = Depends(get_auth_context),
) -> OrgContext:
    if auth.org is None:
        raise HTTPException(403, "Доступно только участникам организации")
    return auth.org


async def require_platform_admin(
    auth: AuthContext = Depends(get_auth_context),
) -> User:
    if not is_platform_admin(auth.user.role):
        raise HTTPException(403, "Доступно только администратору платформы")
    return auth.user


class RequirePermission:
    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(self, auth: AuthContext = Depends(get_auth_context)) -> User:
        org_role = auth.org.org_role if auth.org else None
        if not has_permission(auth.user.role, self.permission, org_role):
            raise HTTPException(403, f"Нет права: {self.permission}")
        return auth.user
