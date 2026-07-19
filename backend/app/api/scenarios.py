import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.scenario import RestoreScenario, RestoreScenarioRun
from app.models.server import Server
from app.schemas.scenario import ScenarioCreate, ScenarioUpdate, ScenarioOut, ScenarioRunOut
from app.services.audit_service import audit_action
from app.services.tenancy_service import apply_org_filter, get_owned_server, is_global_admin
from app.api.deps import get_auth_context, AuthContext

router = APIRouter(
    prefix="/scenarios",
    tags=["scenarios"],
    dependencies=[Depends(get_auth_context)],
)


async def _get_org_scenario(scenario_id: int, auth: AuthContext, db: AsyncSession) -> RestoreScenario:
    sc = await db.get(RestoreScenario, scenario_id)
    if not sc:
        raise HTTPException(404, "Scenario not found")
    if not is_global_admin(auth.user) and (
        auth.org is None or sc.organization_id != auth.org.organization_id
    ):
        raise HTTPException(403, "Нет доступа к этому сценарию")
    return sc


async def _validate_scenario_servers(
    auth: AuthContext,
    db: AsyncSession,
    source_server_id: int,
    target_server_id: int,
) -> None:
    await get_owned_server(source_server_id, auth.user, auth.org, db)
    await get_owned_server(target_server_id, auth.user, auth.org, db)


async def _resolve_scenario_org_id(
    sc: RestoreScenario,
    db: AsyncSession,
    auth: AuthContext,
) -> int:
    if sc.organization_id:
        return sc.organization_id

    source = await db.get(Server, sc.source_server_id)
    if source and source.organization_id:
        sc.organization_id = source.organization_id
        await db.commit()
        return source.organization_id

    target = await db.get(Server, sc.target_server_id)
    if target and target.organization_id:
        sc.organization_id = target.organization_id
        await db.commit()
        return target.organization_id

    if auth.org:
        sc.organization_id = auth.org.organization_id
        await db.commit()
        return auth.org.organization_id

    raise HTTPException(
        400,
        "У сценария не указана организация — Celery-задача не будет обработана. "
        "Назначьте организацию серверам сценария или пересоздайте сценарий в контексте организации.",
    )


async def _enrich_scenario(scenario: RestoreScenario, db: AsyncSession, last_run: RestoreScenarioRun | None = None) -> dict:
    source_server = await db.get(Server, scenario.source_server_id)
    target_server = await db.get(Server, scenario.target_server_id)
    return {
        "id": scenario.id,
        "name": scenario.name,
        "source_server_id": scenario.source_server_id,
        "source_server_name": source_server.name if source_server else None,
        "source_database": scenario.source_database,
        "target_server_id": scenario.target_server_id,
        "target_server_name": target_server.name if target_server else None,
        "target_database": scenario.target_database,
        "old_db_action": scenario.old_db_action,
        "excluded_tables": json.loads(scenario.excluded_tables_json or "[]"),
        "cron_expression": scenario.cron_expression,
        "is_active": scenario.is_active,
        "created_at": scenario.created_at,
        "last_run": last_run,
        "reuse_dump_available": bool(scenario.reuse_dump_path),
        "reuse_dump_size": scenario.reuse_dump_size,
        "reuse_dump_at": scenario.reuse_dump_at,
    }


@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    stmt = apply_org_filter(select(RestoreScenario), auth.user, auth.org, RestoreScenario.organization_id)
    result = await db.execute(stmt.order_by(RestoreScenario.id))
    scenarios = result.scalars().all()

    out = []
    for sc in scenarios:
        last_run_result = await db.execute(
            select(RestoreScenarioRun)
            .where(RestoreScenarioRun.scenario_id == sc.id)
            .order_by(RestoreScenarioRun.started_at.desc())
            .limit(1)
        )
        last_run = last_run_result.scalar_one_or_none()
        out.append(await _enrich_scenario(sc, db, last_run))
    return out


@router.post("", response_model=ScenarioOut, status_code=201)
async def create_scenario(
    data: ScenarioCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.org is None:
        raise HTTPException(403, "Создание сценариев доступно участникам организации")
    await _validate_scenario_servers(auth, db, data.source_server_id, data.target_server_id)
    payload = data.model_dump()
    excluded = payload.pop("excluded_tables", [])
    sc = RestoreScenario(
        **payload,
        organization_id=auth.org.organization_id,
        excluded_tables_json=json.dumps(excluded),
    )
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="scenario",
        entity_id=sc.id,
        payload={"name": sc.name},
        organization_id=auth.org.organization_id,
    )
    return await _enrich_scenario(sc, db)


@router.put("/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(
    scenario_id: int,
    data: ScenarioUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await _get_org_scenario(scenario_id, auth, db)
    payload = data.model_dump(exclude_none=True)
    if "source_server_id" in payload or "target_server_id" in payload:
        src = payload.get("source_server_id", sc.source_server_id)
        tgt = payload.get("target_server_id", sc.target_server_id)
        await _validate_scenario_servers(auth, db, src, tgt)
    if "excluded_tables" in payload:
        sc.excluded_tables_json = json.dumps(payload.pop("excluded_tables"))
    for field, value in payload.items():
        setattr(sc, field, value)
    await db.commit()
    await db.refresh(sc)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="scenario",
        entity_id=sc.id,
        payload=data.model_dump(exclude_none=True),
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return await _enrich_scenario(sc, db)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await _get_org_scenario(scenario_id, auth, db)
    scenario_name = sc.name
    await db.delete(sc)
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="scenario",
        entity_id=scenario_id,
        payload={"name": scenario_name},
        organization_id=auth.org.organization_id if auth.org else None,
    )


@router.post("/{scenario_id}/run", status_code=202)
async def run_scenario_now(
    scenario_id: int,
    request: Request,
    reuse_dump: bool = False,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await _get_org_scenario(scenario_id, auth, db)

    running_result = await db.execute(
        select(RestoreScenarioRun)
        .where(
            RestoreScenarioRun.scenario_id == scenario_id,
            RestoreScenarioRun.status == "running",
        )
        .limit(1)
    )
    if running_result.scalar_one_or_none():
        raise HTTPException(409, "Scenario is already running")

    from app.tasks.scenario_tasks import run_scenario_task
    from app.tasks.queues import enqueue_org_task
    org_id = await _resolve_scenario_org_id(sc, db, auth)
    task = enqueue_org_task(run_scenario_task, org_id, scenario_id, reuse_dump)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="scenario",
        entity_id=scenario_id,
        payload={"operation": "run", "task_id": task.id, "reuse_dump": reuse_dump},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"task_id": task.id, "scenario_id": scenario_id}


@router.post("/runs/{run_id}/stop", status_code=200)
async def stop_scenario_run(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    run = await db.get(RestoreScenarioRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    await _get_org_scenario(run.scenario_id, auth, db)
    if run.status != "running":
        raise HTTPException(409, "Run is not in running state")
    if run.task_id:
        from app.tasks.celery_app import celery
        celery.control.revoke(run.task_id, terminate=True, signal="SIGTERM")
    run.status = "failed"
    run.error_message = "Остановлено пользователем"
    run.finished_at = datetime.utcnow()
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="scenario",
        entity_id=run.scenario_id,
        payload={"operation": "stop", "run_id": run_id},
        result="failed",
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"status": "ok", "run_id": run_id}


@router.get("/{scenario_id}/runs", response_model=list[ScenarioRunOut])
async def list_scenario_runs(
    scenario_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    await _get_org_scenario(scenario_id, auth, db)
    result = await db.execute(
        select(RestoreScenarioRun)
        .where(RestoreScenarioRun.scenario_id == scenario_id)
        .order_by(RestoreScenarioRun.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
