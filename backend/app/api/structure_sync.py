import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.structure_sync import StructureSyncScenario, StructureSyncRun
from app.models.server import Server
from app.schemas.structure_sync import (
    StructureSyncCreate,
    StructureSyncUpdate,
    StructureSyncOut,
    StructureSyncRunOut,
)
from app.services.audit_service import audit_action
from app.services.tenancy_service import apply_org_filter, get_owned_server, is_global_admin
from app.api.deps import get_auth_context, AuthContext

router = APIRouter(
    prefix="/structure-sync",
    tags=["structure-sync"],
    dependencies=[Depends(get_auth_context)],
)


async def _get_owned(scenario_id: int, auth: AuthContext, db: AsyncSession) -> StructureSyncScenario:
    sc = await db.get(StructureSyncScenario, scenario_id)
    if not sc:
        raise HTTPException(404, "Scenario not found")
    if not is_global_admin(auth.user) and (
        auth.org is None or sc.organization_id != auth.org.organization_id
    ):
        raise HTTPException(403, "Нет доступа к этому сценарию")
    return sc


async def _validate_servers(auth: AuthContext, db: AsyncSession, prod_id: int, test_id: int) -> None:
    await get_owned_server(prod_id, auth.user, auth.org, db)
    await get_owned_server(test_id, auth.user, auth.org, db)


async def _enrich(sc: StructureSyncScenario, db: AsyncSession,
                  last_run: StructureSyncRun | None = None) -> dict:
    prod = await db.get(Server, sc.prod_server_id)
    test = await db.get(Server, sc.test_server_id)
    target = await db.get(Server, sc.target_server_id)
    return {
        "id": sc.id,
        "name": sc.name,
        "prod_server_id": sc.prod_server_id,
        "prod_server_name": prod.name if prod else None,
        "prod_database": sc.prod_database,
        "test_server_id": sc.test_server_id,
        "test_server_name": test.name if test else None,
        "test_database": sc.test_database,
        "target_server_id": sc.target_server_id,
        "target_server_name": target.name if target else None,
        "target_name": sc.target_name,
        "temp_name_template": sc.temp_name_template,
        "old_db_prefix": sc.old_db_prefix,
        "keep_old_count": sc.keep_old_count,
        "data_copy_mode": sc.data_copy_mode,
        "excluded_tables": json.loads(sc.excluded_tables_json or "[]"),
        "require_approval": sc.require_approval,
        "cron_expression": sc.cron_expression,
        "is_active": sc.is_active,
        "created_at": sc.created_at,
        "last_run": StructureSyncRunOut.model_validate(last_run) if last_run else None,
    }


async def _last_run(scenario_id: int, db: AsyncSession) -> StructureSyncRun | None:
    res = await db.execute(
        select(StructureSyncRun)
        .where(StructureSyncRun.scenario_id == scenario_id)
        .order_by(StructureSyncRun.started_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


@router.get("", response_model=list[StructureSyncOut])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    stmt = apply_org_filter(
        select(StructureSyncScenario), auth.user, auth.org,
        StructureSyncScenario.organization_id,
    )
    result = await db.execute(stmt.order_by(StructureSyncScenario.id))
    out = []
    for sc in result.scalars().all():
        out.append(await _enrich(sc, db, await _last_run(sc.id, db)))
    return out


@router.post("", response_model=StructureSyncOut, status_code=201)
async def create_scenario(
    data: StructureSyncCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.org is None:
        raise HTTPException(403, "Создание сценариев доступно участникам организации")
    await _validate_servers(auth, db, data.prod_server_id, data.test_server_id)
    payload = data.model_dump()
    # Приёмник: если не задан — по умолчанию prod (in-place, как раньше).
    # Если задан — проверяем, что сервер принадлежит организации.
    if payload.get("target_server_id") is None:
        payload["target_server_id"] = payload["prod_server_id"]
    else:
        await get_owned_server(payload["target_server_id"], auth.user, auth.org, db)
    excluded = payload.pop("excluded_tables", [])
    sc = StructureSyncScenario(
        **payload,
        organization_id=auth.org.organization_id,
        excluded_tables_json=json.dumps(excluded),
    )
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    await audit_action(
        db, user=auth.user, request=request, action="create",
        entity_type="structure_sync", entity_id=sc.id, payload={"name": sc.name},
        organization_id=auth.org.organization_id,
    )
    return await _enrich(sc, db)


@router.put("/{scenario_id}", response_model=StructureSyncOut)
async def update_scenario(
    scenario_id: int,
    data: StructureSyncUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await _get_owned(scenario_id, auth, db)
    payload = data.model_dump(exclude_none=True)
    if "prod_server_id" in payload or "test_server_id" in payload:
        await _validate_servers(
            auth, db,
            payload.get("prod_server_id", sc.prod_server_id),
            payload.get("test_server_id", sc.test_server_id),
        )
    if payload.get("target_server_id") is not None:
        await get_owned_server(payload["target_server_id"], auth.user, auth.org, db)
    if "excluded_tables" in payload:
        sc.excluded_tables_json = json.dumps(payload.pop("excluded_tables"))
    for field, value in payload.items():
        setattr(sc, field, value)
    await db.commit()
    await db.refresh(sc)
    await audit_action(
        db, user=auth.user, request=request, action="update",
        entity_type="structure_sync", entity_id=sc.id, payload=payload,
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return await _enrich(sc, db)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await _get_owned(scenario_id, auth, db)
    name = sc.name
    await db.delete(sc)
    await db.commit()
    await audit_action(
        db, user=auth.user, request=request, action="delete",
        entity_type="structure_sync", entity_id=scenario_id, payload={"name": name},
        organization_id=auth.org.organization_id if auth.org else None,
    )


@router.post("/{scenario_id}/run", status_code=202)
async def run_now(
    scenario_id: int,
    request: Request,
    dry_run: bool = False,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    sc = await _get_owned(scenario_id, auth, db)
    if sc.organization_id is None:
        raise HTTPException(400, "У сценария не указана организация")

    # Снимаем блокировку от зависших queued (воркер не подхватил) до проверки,
    # иначе застрявший прогон вечно давал бы 409. running не трогаем.
    from app.tasks.structure_sync_tasks import STALE_QUEUED_SECONDS
    stale_before = datetime.utcnow() - timedelta(seconds=STALE_QUEUED_SECONDS)
    await db.execute(
        update(StructureSyncRun)
        .where(
            StructureSyncRun.scenario_id == scenario_id,
            StructureSyncRun.status == "queued",
            StructureSyncRun.started_at < stale_before,
        )
        .values(
            status="failed",
            error_message="Задача не подхвачена воркером (таймаут очереди)",
            finished_at=datetime.utcnow(),
        )
    )
    await db.commit()

    running = await db.execute(
        select(StructureSyncRun).where(
            StructureSyncRun.scenario_id == scenario_id,
            StructureSyncRun.status.in_(["queued", "running", "awaiting_approval"]),
        ).limit(1)
    )
    if running.scalar_one_or_none():
        raise HTTPException(409, "Сценарий уже выполняется или ждёт подтверждения")

    # Строку прогона создаём синхронно ДО enqueue: повторный клик тут же упрётся
    # в проверку выше (статус queued), а не проскочит, пока задача ещё не стартовала.
    run = StructureSyncRun(
        scenario_id=scenario_id,
        status="queued",
        current_step="queued",
        dry_run=dry_run,
        dropped_old_json="[]",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    try:
        await db.commit()
    except IntegrityError:
        # Гонка: параллельный запрос уже создал активный прогон — ловит
        # частичный уникальный индекс uq_structure_sync_active_run.
        await db.rollback()
        raise HTTPException(409, "Сценарий уже выполняется или ждёт подтверждения")
    await db.refresh(run)

    from app.tasks.structure_sync_tasks import run_structure_sync_task
    from app.tasks.queues import enqueue_org_task
    try:
        task = enqueue_org_task(
            run_structure_sync_task, sc.organization_id, scenario_id,
            run_id=run.id, dry_run=dry_run,
        )
    except Exception as e:  # noqa: BLE001
        # Не оставляем «застрявший» queued — иначе он навсегда заблокирует перезапуск.
        run.status = "failed"
        run.error_message = f"Не удалось поставить задачу в очередь: {e}"[:5000]
        run.finished_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(503, "Не удалось поставить задачу в очередь") from e
    run.task_id = task.id
    await db.commit()
    await audit_action(
        db, user=auth.user, request=request, action="execute",
        entity_type="structure_sync", entity_id=scenario_id,
        payload={"operation": "dry_run" if dry_run else "run",
                 "task_id": task.id, "run_id": run.id},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"task_id": task.id, "run_id": run.id, "scenario_id": scenario_id, "dry_run": dry_run}


@router.post("/runs/{run_id}/approve", status_code=202)
async def approve_run(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    run = await db.get(StructureSyncRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    sc = await _get_owned(run.scenario_id, auth, db)
    # свап prod — только org_admin или админ платформы
    if not is_global_admin(auth.user) and (auth.org is None or auth.org.org_role != "org_admin"):
        raise HTTPException(403, "Подтверждение свапа доступно только администратору организации")

    # Атомарный захват: только один approve переведёт awaiting_approval → running.
    # Второй одновременный approve получит rowcount=0 → 409, свап не задвоится.
    result = await db.execute(
        update(StructureSyncRun)
        .where(StructureSyncRun.id == run_id, StructureSyncRun.status == "awaiting_approval")
        .values(status="running")
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(409, "Прогон не ждёт подтверждения")

    from app.tasks.structure_sync_tasks import run_structure_sync_swap_task
    from app.tasks.queues import enqueue_org_task
    task = enqueue_org_task(run_structure_sync_swap_task, sc.organization_id, run_id)
    await audit_action(
        db, user=auth.user, request=request, action="execute",
        entity_type="structure_sync", entity_id=run.scenario_id,
        payload={"operation": "approve_swap", "run_id": run_id, "task_id": task.id},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"task_id": task.id, "run_id": run_id}


@router.post("/runs/{run_id}/reject", status_code=200)
async def reject_run(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    run = await db.get(StructureSyncRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    await _get_owned(run.scenario_id, auth, db)

    # Атомарный отказ: только из awaiting_approval → failed. При одновременном
    # approve выигрывает тот, чей UPDATE прошёл первым; второй получит 409.
    result = await db.execute(
        update(StructureSyncRun)
        .where(StructureSyncRun.id == run_id, StructureSyncRun.status == "awaiting_approval")
        .values(
            status="failed",
            error_message=f"Свап отклонён пользователем. temp остаётся: {run.temp_db}",
            finished_at=datetime.utcnow(),
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(409, "Прогон не ждёт подтверждения")
    await audit_action(
        db, user=auth.user, request=request, action="execute",
        entity_type="structure_sync", entity_id=run.scenario_id,
        payload={"operation": "reject_swap", "run_id": run_id}, result="failed",
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"status": "rejected", "run_id": run_id, "temp_db": run.temp_db}


@router.post("/runs/{run_id}/stop", status_code=200)
async def stop_run(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    run = await db.get(StructureSyncRun, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    sc = await _get_owned(run.scenario_id, auth, db)
    if run.status not in ("queued", "running"):
        raise HTTPException(409, "Прогон не выполняется")
    if run.current_step == "swap":
        # Прерывание между rename(target→to_delete__…) и rename(temp→target)
        # оставит боевую БД без имени target — свап не останавливаем.
        raise HTTPException(409, "Идёт свап имён БД — остановка небезопасна")
    if run.task_id:
        from app.tasks.celery_app import celery
        celery.control.revoke(run.task_id, terminate=True, signal="SIGTERM")
    run.status = "failed"
    run.error_message = "Остановлено пользователем"
    run.finished_at = datetime.utcnow()
    await db.commit()
    # SIGTERM убивает задачу до того, как её except опубликует событие, поэтому
    # шлём structure_sync_failed сами — иначе карточка задачи висит на этапе.
    from app.services.event_bus import publish_org_event
    if sc.organization_id:
        publish_org_event(sc.organization_id, "structure_sync_failed", {
            "task_id": run.task_id,
            "run_id": run.id,
            "scenario_id": run.scenario_id,
            "error": "Остановлено пользователем",
        })
    await audit_action(
        db, user=auth.user, request=request, action="execute",
        entity_type="structure_sync", entity_id=run.scenario_id,
        payload={"operation": "stop", "run_id": run_id}, result="failed",
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return {"status": "stopped", "run_id": run_id}


@router.get("/{scenario_id}/runs", response_model=list[StructureSyncRunOut])
async def list_runs(
    scenario_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    await _get_owned(scenario_id, auth, db)
    result = await db.execute(
        select(StructureSyncRun)
        .where(StructureSyncRun.scenario_id == scenario_id)
        .order_by(StructureSyncRun.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
