from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.api.deps import RequirePermission, AuthContext, get_auth_context
from app.services.audit_service import audit_action
from app.tasks.queues import delete_org_queue_by_slug

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/organizations")
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("view_all")),
):
    orgs = (await db.execute(select(Organization).order_by(Organization.id))).scalars().all()
    out = []
    for org in orgs:
        cnt = await db.execute(
            select(func.count(OrganizationMember.id))
            .where(OrganizationMember.organization_id == org.id)
        )
        out.append({
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "created_at": org.created_at,
            "members_count": cnt.scalar_one(),
        })
    return out


@router.delete("/organizations/{org_id}", status_code=204)
async def delete_organization(
    org_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("manage_users")),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    slug = org.slug
    name = org.name
    await db.delete(org)
    await db.commit()
    delete_org_queue_by_slug(slug)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="organization",
        entity_id=org_id,
        payload={"name": name, "slug": slug},
        organization_id=None,
    )


@router.get("/users")
async def list_all_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(RequirePermission("manage_users")),
):
    users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    out = []
    for u in users:
        memberships = await db.execute(
            select(OrganizationMember, Organization.name)
            .join(Organization, Organization.id == OrganizationMember.organization_id)
            .where(OrganizationMember.user_id == u.id)
        )
        orgs = [
            {"organization_id": m.organization_id, "organization_name": name, "org_role": m.org_role, "is_active": m.is_active}
            for m, name in memberships.all()
        ]
        out.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "organizations": orgs,
        })
    return out
