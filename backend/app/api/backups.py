from datetime import datetime

import redis as sync_redis
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.backup import BackupSchedule, BackupHistory, RestoreHistory
from app.models.server import Server
from app.models.minio_config import MinioConfig
from app.models.user import User
from app.schemas.backup import (
    BackupRequest, BackupScheduleCreate, BackupScheduleOut,
    BackupHistoryOut, RestoreHistoryOut, RestoreRequest, BackupDeleteBulkRequest,
)
from sqlalchemy import delete as sa_delete
from app.tasks.backup_tasks import run_backup_task, run_restore_task
from app.tasks.celery_app import celery
from app.tasks.queues import enqueue_org_task
from app.api.deps import get_auth_context, RequirePermission, AuthContext
from app.services import minio_service
from app.services.audit_service import audit_action
from app.services.tenancy_service import get_owned_server, accessible_server_ids, ensure_database_access

router = APIRouter(prefix="/backups", tags=["backups"])


async def _ensure_accessible_server(server_id: int, auth: AuthContext, db: AsyncSession) -> None:
    await get_owned_server(server_id, auth.user, auth.org, db)


async def _ensure_accessible_backup(backup_id: int, auth: AuthContext, db: AsyncSession) -> BackupHistory:
    backup = await db.get(BackupHistory, backup_id)
    if not backup:
        raise HTTPException(404, "Backup not found")
    await get_owned_server(backup.server_id, auth.user, auth.org, db)
    return backup


def _filter_by_accessible_servers(stmt, server_ids: list[int] | None, server_column):
    if server_ids is not None:
        if not server_ids:
            return stmt.where(server_column == -1)
        stmt = stmt.where(server_column.in_(server_ids))
    return stmt


def _org_id(auth: AuthContext) -> int | None:
    return auth.org.organization_id if auth.org else None


def _validate_backup_server(server: Server) -> None:
    if not server.organization_id:
        raise HTTPException(
            400,
            "У сервера не указана организация — Celery-задача не будет обработана. "
            "Пересоздайте сервер в контексте организации или назначьте organization_id в БД.",
        )


async def _resolve_storage_ids(
    server: Server,
    storage_ids: list[int] | None,
    db: AsyncSession,
    org_id: int | None,
) -> list[int]:
    if storage_ids:
        seen: set[int] = set()
        resolved: list[int] = []
        for sid in storage_ids:
            if sid in seen:
                continue
            seen.add(sid)
            storage = await db.get(MinioConfig, sid)
            if not storage:
                raise HTTPException(404, f"Хранилище #{sid} не найдено")
            if org_id is not None and storage.organization_id != org_id:
                raise HTTPException(400, f"Хранилище «{storage.name}» не принадлежит вашей организации")
            if not minio_service.is_storage_configured(sid):
                raise HTTPException(400, f"Хранилище «{storage.name}» не настроено")
            resolved.append(sid)
        if not resolved:
            raise HTTPException(400, "Выберите хотя бы одно хранилище")
        return resolved
    if server.storage_id:
        storage = await db.get(MinioConfig, server.storage_id)
        if not storage:
            raise HTTPException(
                400,
                "Хранилище по умолчанию сервера не найдено. Выберите хранилища при запуске бэкапа.",
            )
        if org_id is not None and storage.organization_id != org_id:
            raise HTTPException(400, "Хранилище по умолчанию не принадлежит вашей организации")
        if not minio_service.is_storage_configured(server.storage_id):
            raise HTTPException(400, "Хранилище по умолчанию сервера не настроено")
        return [server.storage_id]
    raise HTTPException(
        400,
        "Не выбраны хранилища и у сервера нет хранилища по умолчанию. "
        "Выберите хранилища при запуске или привяжите хранилище к серверу в «Настройки → Хранилище».",
    )


@router.get("/running")
async def get_running_backups(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    """Возвращает все running-бэкапы с текущим stage для восстановления состояния UI после рефреша."""
    server_ids = await accessible_server_ids(auth.user, auth.org, db)
    stmt = (
        select(BackupHistory, Server.name.label("server_name"))
        .join(Server, Server.id == BackupHistory.server_id)
        .where(BackupHistory.status == "running")
    )
    stmt = _filter_by_accessible_servers(stmt, server_ids, BackupHistory.server_id)
    result = await db.execute(stmt.order_by(BackupHistory.started_at.desc()))
    rows = result.all()
    return [
        {
            "id": h.id,
            "task_id": h.task_id,
            "server_id": h.server_id,
            "server_name": server_name,
            "database_name": h.database_name,
            "stage": h.stage or "preparing",
            "started_at": h.started_at.isoformat() if h.started_at else None,
        }
        for h, server_name in rows
    ]


@router.post("/run")
async def trigger_backup(
    data: BackupRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    await _ensure_accessible_server(data.server_id, auth, db)
    if auth.org is not None:
        await ensure_database_access(auth.org, data.server_id, data.database_name, db)
    server = await db.get(Server, data.server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    _validate_backup_server(server)
    storage_ids = await _resolve_storage_ids(server, data.storage_ids, db, _org_id(auth))
    try:
        task = enqueue_org_task(
            run_backup_task, server.organization_id,
            data.server_id, data.database_name, data.backup_format, data.excluded_tables,
            storage_ids,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="backup",
        payload={
            "operation": "run",
            "server_id": data.server_id,
            "database_name": data.database_name,
            "format": data.backup_format,
            "storage_ids": storage_ids,
            "task_id": task.id,
        },
        organization_id=_org_id(auth),
    )
    return {"task_id": task.id, "status": "queued"}


@router.post("/restore")
async def trigger_restore(
    data: RestoreRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_restore")),
):
    backup = await _ensure_accessible_backup(data.backup_id, auth, db)
    if not backup.file_path:
        raise HTTPException(404, "Backup not found")
    await _ensure_accessible_server(data.server_id, auth, db)
    if auth.org is not None:
        await ensure_database_access(auth.org, data.server_id, data.database_name, db)
    fmt = backup.backup_format or "custom"
    server = await db.get(Server, data.server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    if not server.organization_id:
        raise HTTPException(400, "У сервера не указана организация")
    try:
        task = enqueue_org_task(
            run_restore_task, server.organization_id,
            data.server_id, data.database_name, backup.file_path, fmt, backup.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="backup",
        entity_id=backup.id,
        payload={
            "operation": "restore",
            "server_id": data.server_id,
            "database_name": data.database_name,
            "task_id": task.id,
        },
        organization_id=_org_id(auth),
    )
    return {"task_id": task.id, "status": "queued"}


@router.get("/task/{task_id}")
async def get_task_status(
    task_id: str,
    auth: AuthContext = Depends(get_auth_context),
):
    result = celery.AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": result.status,
        "result": None,
    }
    if result.ready():
        response["result"] = result.result
    return response


@router.get("/queue")
async def get_queue_info(auth: AuthContext = Depends(get_auth_context)):
    inspector = celery.control.inspect()
    active = inspector.active() or {}
    reserved = inspector.reserved() or {}
    scheduled = inspector.scheduled() or {}

    def _format_tasks(worker_tasks: dict) -> list[dict]:
        result = []
        for worker, tasks in worker_tasks.items():
            for t in tasks:
                result.append({
                    "task_id": t.get("id", ""),
                    "name": t.get("name", t.get("type", "")),
                    "args": t.get("args", []),
                    "kwargs": t.get("kwargs", {}),
                    "worker": worker,
                    "started": t.get("time_start"),
                    "eta": t.get("eta"),
                })
        return result

    return {
        "active": _format_tasks(active),
        "reserved": _format_tasks(reserved),
        "scheduled": _format_tasks(scheduled),
    }


@router.post("/task/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    celery.control.revoke(task_id, terminate=True, signal="SIGTERM")

    result = await db.execute(
        select(BackupHistory).where(
            BackupHistory.task_id == task_id,
            BackupHistory.status == "running",
        )
    )
    backups = result.scalars().all()
    if backups:
        r = sync_redis.from_url(settings.redis_url)
        try:
            for backup in backups:
                backup.status = "failed"
                backup.stage = "aborted"
                backup.error_message = "Отменено пользователем"
                backup.finished_at = datetime.utcnow()
                lock_key = f"pgadmin:lock:backup:{backup.server_id}:{backup.database_name}"
                r.delete(lock_key)
        finally:
            r.close()
        await db.commit()

    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="backup",
        payload={"operation": "cancel_task", "task_id": task_id},
        organization_id=_org_id(auth),
    )
    return {"task_id": task_id, "status": "cancelled"}


@router.get("/schedules", response_model=list[BackupScheduleOut])
async def list_schedules(
    server_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server_ids = await accessible_server_ids(auth.user, auth.org, db)
    q = select(BackupSchedule)
    if server_id:
        await _ensure_accessible_server(server_id, auth, db)
        q = q.where(BackupSchedule.server_id == server_id)
    q = _filter_by_accessible_servers(q, server_ids, BackupSchedule.server_id)
    result = await db.execute(q.order_by(BackupSchedule.id))
    return result.scalars().all()


@router.post("/schedules", response_model=BackupScheduleOut, status_code=201)
async def create_schedule(
    data: BackupScheduleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    await _ensure_accessible_server(data.server_id, auth, db)
    if auth.org is not None:
        await ensure_database_access(auth.org, data.server_id, data.database_name, db)
    server = await db.get(Server, data.server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    _validate_backup_server(server)
    storage_ids = await _resolve_storage_ids(server, data.storage_ids, db, _org_id(auth))
    payload = data.model_dump()
    payload["storage_ids"] = storage_ids
    schedule = BackupSchedule(**payload)
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="backup_schedule",
        entity_id=schedule.id,
        payload=data.model_dump(),
        organization_id=_org_id(auth),
    )
    return schedule


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    schedule = await db.get(BackupSchedule, schedule_id)
    if not schedule:
        raise HTTPException(404, "Schedule not found")
    await _ensure_accessible_server(schedule.server_id, auth, db)
    await db.delete(schedule)
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="backup_schedule",
        entity_id=schedule_id,
        organization_id=_org_id(auth),
    )


@router.post("/history/{backup_id}/abort", status_code=200)
async def abort_backup(
    backup_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    """Принудительно переводит зависший running-бэкап в статус failed."""
    backup = await _ensure_accessible_backup(backup_id, auth, db)
    if backup.status != "running":
        raise HTTPException(400, f"Backup is not running (status={backup.status})")
    from datetime import datetime
    backup.status = "failed"
    backup.stage = "aborted"
    backup.error_message = "Принудительно завершён пользователем"
    backup.finished_at = datetime.utcnow()
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="execute",
        entity_type="backup",
        entity_id=backup_id,
        payload={"operation": "abort"},
        result="failed",
        organization_id=_org_id(auth),
    )
    return {"id": backup_id, "status": "failed"}


def _history_out(history: BackupHistory, storage_name: str | None = None) -> BackupHistoryOut:
    return BackupHistoryOut(
        id=history.id,
        server_id=history.server_id,
        database_name=history.database_name,
        status=history.status,
        stage=history.stage,
        task_id=history.task_id,
        backup_format=history.backup_format,
        file_path=history.file_path,
        storage_id=history.storage_id,
        storage_name=storage_name,
        file_size=history.file_size,
        checksum=history.checksum,
        duration_seconds=history.duration_seconds,
        error_message=history.error_message,
        started_at=history.started_at,
        finished_at=history.finished_at,
    )


@router.get("/history", response_model=list[BackupHistoryOut])
async def list_history(
    server_id: int | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server_ids = await accessible_server_ids(auth.user, auth.org, db)
    q = (
        select(BackupHistory, MinioConfig.name.label("storage_name"))
        .outerjoin(MinioConfig, MinioConfig.id == BackupHistory.storage_id)
    )
    if server_id:
        await _ensure_accessible_server(server_id, auth, db)
        q = q.where(BackupHistory.server_id == server_id)
    q = _filter_by_accessible_servers(q, server_ids, BackupHistory.server_id)
    result = await db.execute(q.order_by(BackupHistory.started_at.desc()).limit(limit))
    return [_history_out(h, storage_name) for h, storage_name in result.all()]


@router.get("/restore-history", response_model=list[RestoreHistoryOut])
async def list_restore_history(
    server_id: int | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    server_ids = await accessible_server_ids(auth.user, auth.org, db)
    q = select(RestoreHistory, Server.name.label("server_name")).join(
        Server, Server.id == RestoreHistory.server_id
    )
    if server_id:
        await _ensure_accessible_server(server_id, auth, db)
        q = q.where(RestoreHistory.server_id == server_id)
    q = _filter_by_accessible_servers(q, server_ids, RestoreHistory.server_id)
    result = await db.execute(q.order_by(RestoreHistory.started_at.desc()).limit(limit))
    out: list[RestoreHistoryOut] = []
    for rec, server_name in result.all():
        item = RestoreHistoryOut.model_validate(rec)
        item.server_name = server_name
        out.append(item)
    return out


@router.get("/history/{backup_id}/download")
async def download_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    from fastapi.responses import StreamingResponse
    backup = await _ensure_accessible_backup(backup_id, auth, db)
    if not backup.file_path:
        raise HTTPException(404, "Backup file not found")
    if backup.status != "success":
        raise HTTPException(400, "Backup is not in success state")
    obj_name = _extract_object_name(backup.file_path)
    if not obj_name:
        raise HTTPException(404, "Cannot resolve object name")

    filename = obj_name.split("/")[-1]
    response = minio_service.get_object_stream(
        backup.server_id, obj_name, storage_id=backup.storage_id
    )
    if response is None:
        raise HTTPException(404, "File not found in storage")

    def _stream_and_release():
        # Гарантированно освобождаем соединение пула даже при обрыве клиента
        # (StreamingResponse закроет генератор → finally отработает).
        try:
            for chunk in response.stream(32 * 1024):
                yield chunk
        finally:
            try:
                response.release_conn()
            except Exception:  # noqa: BLE001
                try:
                    response.close()
                except Exception:  # noqa: BLE001
                    pass

    return StreamingResponse(
        _stream_and_release(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _extract_object_name(file_path: str | None) -> str | None:
    """file_path хранится как '{server_name}/{database}/{filename}' — это и есть object_name."""
    return file_path or None


@router.delete("/history/{backup_id}", status_code=204)
async def delete_backup(
    backup_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    backup = await _ensure_accessible_backup(backup_id, auth, db)
    obj_name = _extract_object_name(backup.file_path)
    if obj_name:
        minio_service.delete_file(backup.server_id, obj_name, storage_id=backup.storage_id)
    await db.delete(backup)
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="backup",
        entity_id=backup_id,
        payload={"database_name": backup.database_name, "server_id": backup.server_id},
        organization_id=_org_id(auth),
    )


@router.delete("/history", status_code=204)
async def delete_backups_bulk(
    data: BackupDeleteBulkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
    _: User = Depends(RequirePermission("run_backup")),
):
    if not data.ids:
        return
    server_ids = await accessible_server_ids(auth.user, auth.org, db)
    stmt = select(BackupHistory).where(BackupHistory.id.in_(data.ids))
    stmt = _filter_by_accessible_servers(stmt, server_ids, BackupHistory.server_id)
    result = await db.execute(stmt)
    records = result.scalars().all()
    for rec in records:
        obj_name = _extract_object_name(rec.file_path)
        if obj_name:
            minio_service.delete_file(rec.server_id, obj_name, storage_id=rec.storage_id)
    await db.execute(sa_delete(BackupHistory).where(BackupHistory.id.in_(data.ids)))
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="backup",
        payload={"operation": "bulk_delete", "ids": data.ids},
        organization_id=_org_id(auth),
    )
