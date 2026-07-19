from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.api.deps import get_auth_context, RequirePermission, AuthContext
from app.services.tenancy_service import is_global_admin

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit(
    username: str | None = Query(None),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("view_audit")),
):
    stmt = select(AuditLog)
    if not is_global_admin(auth.user):
        if auth.org is None:
            return []
        stmt = stmt.where(AuditLog.organization_id == auth.org.organization_id)
    if username:
        stmt = stmt.where(AuditLog.username.ilike(f"%{username.strip()}%"))
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
