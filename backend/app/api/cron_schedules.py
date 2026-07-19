from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cron_schedule import CronSchedule
from app.schemas.cron_schedule import CronScheduleCreate, CronScheduleUpdate, CronScheduleOut
from app.services.audit_service import audit_action
from app.services.tenancy_service import is_global_admin
from app.api.deps import get_auth_context, AuthContext

router = APIRouter(
    prefix="/cron-schedules",
    tags=["cron-schedules"],
    dependencies=[Depends(get_auth_context)],
)


@router.get("", response_model=list[CronScheduleOut])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    stmt = select(CronSchedule)
    if not is_global_admin(auth.user):
        if auth.org is None:
            stmt = stmt.where(CronSchedule.is_builtin.is_(True))
        else:
            stmt = stmt.where(
                or_(
                    CronSchedule.is_builtin.is_(True),
                    CronSchedule.organization_id == auth.org.organization_id,
                )
            )
    result = await db.execute(
        stmt.order_by(CronSchedule.is_builtin.desc(), CronSchedule.id)
    )
    return result.scalars().all()


@router.post("", response_model=CronScheduleOut, status_code=201)
async def create_schedule(
    data: CronScheduleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.org is None:
        raise HTTPException(403, "Создание расписаний доступно участникам организации")
    sc = CronSchedule(
        name=data.name,
        cron_expression=data.cron_expression,
        description=data.description,
        is_builtin=False,
        organization_id=auth.org.organization_id,
    )
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="cron_schedule",
        entity_id=sc.id,
        payload={"name": sc.name, "cron_expression": sc.cron_expression},
        organization_id=auth.org.organization_id,
    )
    return sc


@router.put("/{schedule_id}", response_model=CronScheduleOut)
async def update_schedule(
    schedule_id: int,
    data: CronScheduleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await db.get(CronSchedule, schedule_id)
    if not sc:
        raise HTTPException(404, "Schedule not found")
    if sc.is_builtin:
        raise HTTPException(403, "Встроенные расписания нельзя редактировать")
    if not is_global_admin(auth.user) and (
        auth.org is None or sc.organization_id != auth.org.organization_id
    ):
        raise HTTPException(403, "Нет доступа к этому расписанию")
    if data.name is not None:
        sc.name = data.name
    if data.cron_expression is not None:
        sc.cron_expression = data.cron_expression
    if data.description is not None:
        sc.description = data.description
    await db.commit()
    await db.refresh(sc)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="cron_schedule",
        entity_id=sc.id,
        payload=data.model_dump(exclude_unset=True),
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return sc


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await db.get(CronSchedule, schedule_id)
    if not sc:
        raise HTTPException(404, "Schedule not found")
    if sc.is_builtin:
        raise HTTPException(403, "Встроенные расписания нельзя удалять")
    if not is_global_admin(auth.user) and (
        auth.org is None or sc.organization_id != auth.org.organization_id
    ):
        raise HTTPException(403, "Нет доступа к этому расписанию")
    await db.delete(sc)
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="cron_schedule",
        entity_id=schedule_id,
        payload={"name": sc.name},
        organization_id=auth.org.organization_id if auth.org else None,
    )
