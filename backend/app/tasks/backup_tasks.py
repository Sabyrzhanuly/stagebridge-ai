from datetime import datetime, timedelta
import os
import time

from celery.signals import worker_ready
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery
from app.config import settings
from app.models.server import Server
from app.models.backup import BackupSchedule, BackupHistory, RestoreHistory
from app.services.backup_service import create_pg_dump, run_pg_restore
from app.services import minio_service
from app.services.event_bus import publish_org_event
from app.tasks.notification_tasks import fire_event_notifications
from app.tasks.queues import PLATFORM_QUEUE, list_organization_ids, enqueue_org_task

import redis as sync_redis


@worker_ready.connect
def _cleanup_stale_rabbitmq_org_queues(sender=None, **kwargs):
    """Удаляет legacy org_{id} и org-{slug} без организации в БД."""
    try:
        from app.tasks.queues import sync_org_queues_with_db
        sync_org_queues_with_db()
    except Exception:
        pass


@worker_ready.connect
def _cleanup_stale_locks(sender=None, **kwargs):
    """При старте воркера сбрасываем зависшие running-записи и Redis-блокировки."""
    session = _get_sync_session()
    try:
        stale = session.execute(
            select(BackupHistory).where(BackupHistory.status == "running")
        ).scalars().all()
        stale_restores = session.execute(
            select(RestoreHistory).where(RestoreHistory.status == "running")
        ).scalars().all()
        if stale or stale_restores:
            r = sync_redis.from_url(settings.redis_url)
            for rec in stale:
                rec.status = "failed"
                rec.stage = "failed"
                rec.error_message = "Прервано перезапуском воркера"
                rec.finished_at = datetime.utcnow()
                r.delete(f"pgadmin:lock:backup:{rec.server_id}:{rec.database_name}")
            for rec in stale_restores:
                rec.status = "failed"
                rec.error_message = "Прервано перезапуском воркера"
                rec.finished_at = datetime.utcnow()
                r.delete(f"pgadmin:lock:backup:{rec.server_id}:{rec.database_name}")
            r.close()
            session.commit()
    except Exception as e:  # noqa: BLE001
        print(f"[worker_ready] сброс зависших записей не удался: {e}", flush=True)
    finally:
        session.close()


def _get_sync_session() -> Session:
    engine = create_engine(settings.app_db_url_sync)
    return Session(engine)


def _org_id_for_server(session: Session, server_id: int) -> int | None:
    server = session.get(Server, server_id)
    return server.organization_id if server else None


def _publish(org_id: int, event_type: str, data: dict) -> None:
    publish_org_event(org_id, event_type, data)


def _acquire_lock(server_id: int, db_name: str, ttl: int = 3600) -> tuple[bool, str]:
    r = sync_redis.from_url(settings.redis_url)
    key = f"pgadmin:lock:backup:{server_id}:{db_name}"
    acquired = r.set(key, "1", nx=True, ex=ttl)
    if not acquired:
        # Лок занят: «крадём» его только если это осиротевший лок — нет ни живого
        # бэкапа, ни живого восстановления этой БД (общий лок backup ↔ restore).
        session = _get_sync_session()
        try:
            running_backup = session.execute(
                select(BackupHistory).where(
                    BackupHistory.server_id == server_id,
                    BackupHistory.database_name == db_name,
                    BackupHistory.status == "running",
                )
            ).scalars().first()
            running_restore = session.execute(
                select(RestoreHistory).where(
                    RestoreHistory.server_id == server_id,
                    RestoreHistory.database_name == db_name,
                    RestoreHistory.status == "running",
                )
            ).scalars().first()
        finally:
            session.close()
        if running_backup is None and running_restore is None:
            r.delete(key)
            acquired = r.set(key, "1", nx=True, ex=ttl)
    r.close()
    return bool(acquired), key


def _release_lock(key: str) -> None:
    r = sync_redis.from_url(settings.redis_url)
    r.delete(key)
    r.close()


def _finish_restore(rec_id: int, status: str, error: str | None, duration: int | None) -> None:
    session = _get_sync_session()
    try:
        rec = session.get(RestoreHistory, rec_id)
        if rec:
            rec.status = status
            rec.error_message = error
            rec.duration_seconds = duration
            rec.finished_at = datetime.utcnow()
            session.commit()
    except Exception as e:  # noqa: BLE001
        print(f"[restore] не удалось записать финал restore {rec_id}: {e}", flush=True)
    finally:
        session.close()


@celery.task(
    name="app.tasks.backup_tasks.run_backup_task",
    bind=True,
    autoretry_for=(ConnectionError,),
    retry_backoff=True,
    max_retries=3,
)
def run_backup_task(
    self,
    server_id: int,
    database_name: str,
    backup_format: str = "custom",
    excluded_tables: list[str] | None = None,
    storage_ids: list[int] | None = None,
) -> dict:
    task_id = self.request.id
    session = _get_sync_session()
    org_id = _org_id_for_server(session, server_id)

    acquired, lock_key = _acquire_lock(server_id, database_name)
    if not acquired:
        if org_id is not None:
            _publish(org_id, "backup_failed", {
                "task_id": task_id, "server_id": server_id,
                "database": database_name,
                "error": "Backup already running for this database",
            })
        session.close()
        return {"status": "error", "error": "Backup already running for this database"}

    histories: list[BackupHistory] = []
    primary: BackupHistory | None = None
    dump_result = None

    try:
        server = session.get(Server, server_id)
        if not server:
            return {"status": "error", "error": "Server not found"}
        if not server.organization_id:
            if org_id is not None:
                _publish(org_id, "backup_failed", {
                    "task_id": task_id, "server_id": server_id,
                    "database": database_name,
                    "error": "У сервера не указана организация",
                })
            return {"status": "error", "error": "У сервера не указана организация"}

        resolved_storage_ids = list(storage_ids or [])
        if not resolved_storage_ids:
            if server.storage_id:
                resolved_storage_ids = [server.storage_id]
            else:
                err = "Не указаны хранилища для загрузки бэкапа"
                if org_id is not None:
                    _publish(org_id, "backup_failed", {
                        "task_id": task_id, "server_id": server_id,
                        "server_name": server.name,
                        "database": database_name, "error": err,
                    })
                return {"status": "error", "error": err}

        for sid in resolved_storage_ids:
            if not minio_service.is_storage_configured(sid):
                err = f"Хранилище #{sid} не настроено"
                if org_id is not None:
                    _publish(org_id, "backup_failed", {
                        "task_id": task_id, "server_id": server_id,
                        "server_name": server.name,
                        "database": database_name, "error": err,
                    })
                return {"status": "error", "error": err}

        org_id = server.organization_id

        from app.services.backup_service import get_db_size
        db_size = get_db_size(server, database_name)

        for sid in resolved_storage_ids:
            history = BackupHistory(
                server_id=server_id,
                database_name=database_name,
                backup_format=backup_format,
                task_id=task_id,
                storage_id=sid,
                status="running",
                started_at=datetime.utcnow(),
            )
            session.add(history)
            histories.append(history)
        session.commit()
        primary = histories[0]

        _publish(org_id, "backup_started", {
            "id": primary.id, "task_id": task_id,
            "server_id": server_id, "server_name": server.name,
            "database": database_name, "started_at": datetime.utcnow().isoformat(),
            "total_bytes": db_size,
            "backup_format": backup_format,
            "storage_count": len(resolved_storage_ids),
        })

        def _on_progress(kind: str, data: dict):
            _publish(org_id, "backup_progress", {
                "id": primary.id, "task_id": task_id, "kind": kind, **data,
            })

        def _update_stage(stage_name: str):
            for history in histories:
                history.stage = stage_name
            session.commit()
            _publish(org_id, "backup_progress", {
                "id": primary.id, "task_id": task_id,
                "kind": "stage", "stage": stage_name,
            })

        dump_result = create_pg_dump(
            server, database_name,
            backup_format=backup_format,
            excluded_tables=excluded_tables or [],
            on_progress=_on_progress,
            stage_callback=_update_stage,
        )

        _update_stage("uploading")
        upload_errors: list[str] = []
        task_start = datetime.utcnow()
        total = len(resolved_storage_ids)

        for idx, (history, sid) in enumerate(zip(histories, resolved_storage_ids), start=1):
            _on_progress("phase", {
                "phase": "upload_started",
                "message": f"Загрузка {idx}/{total}: {dump_result.object_name}",
                "storage_id": sid,
                "upload_index": idx,
                "upload_total": total,
            })
            try:
                minio_service.upload_file(
                    server_id,
                    dump_result.tmp_path,
                    dump_result.object_name,
                    storage_id=sid,
                )
                duration = int((datetime.utcnow() - task_start).total_seconds())
                history.status = "success"
                history.stage = "completed"
                history.file_path = dump_result.object_name
                history.file_size = dump_result.file_size
                history.checksum = dump_result.checksum
                history.duration_seconds = duration
                history.finished_at = datetime.utcnow()
                session.commit()
                _on_progress("phase", {
                    "phase": "upload_completed",
                    "message": f"Загружено в хранилище {idx}/{total}",
                    "storage_id": sid,
                    "upload_index": idx,
                    "upload_total": total,
                })
                _publish(org_id, "backup_completed", {
                    "id": history.id, "task_id": task_id, "status": "success",
                    "server_id": server_id, "server_name": server.name,
                    "database": database_name, "file_path": dump_result.object_name,
                    "size": dump_result.file_size, "duration": duration,
                    "checksum": dump_result.checksum,
                    "storage_id": sid,
                    "finished_at": datetime.utcnow().isoformat(),
                })
            except Exception as upload_err:
                err_text = str(upload_err)
                upload_errors.append(err_text)
                history.status = "failed"
                history.stage = "failed"
                history.error_message = err_text
                history.finished_at = datetime.utcnow()
                session.commit()
                _publish(org_id, "backup_failed", {
                    "id": history.id, "task_id": task_id,
                    "server_id": server_id, "server_name": server.name,
                    "database": database_name, "error": err_text,
                    "storage_id": sid,
                    "finished_at": datetime.utcnow().isoformat(),
                })

        if upload_errors:
            if len(upload_errors) == len(resolved_storage_ids):
                raise RuntimeError("; ".join(upload_errors))
            size_str = f"{dump_result.file_size / 1024 / 1024:.1f} MB" if dump_result.file_size else "?"
            fire_event_notifications(
                session, "backup_failed", server_id,
                f"⚠️ <b>Бэкап частично завершён</b>\n🖥 Сервер: <code>{server.name}</code>\n"
                f"🗄 База: <code>{database_name}</code>\n"
                f"📦 Успешно: {len(resolved_storage_ids) - len(upload_errors)}/{len(resolved_storage_ids)}\n"
                f"📋 {upload_errors[0][:200]}",
            )
            return {
                "status": "partial",
                "file_path": dump_result.object_name,
                "checksum": dump_result.checksum,
                "errors": upload_errors,
            }

        size_str = f"{dump_result.file_size / 1024 / 1024:.1f} MB" if dump_result.file_size else "?"
        duration = histories[0].duration_seconds or 0
        fire_event_notifications(
            session, "backup_success", server_id,
            f"✅ <b>Бэкап завершён</b>\n🖥 Сервер: <code>{server.name}</code>\n"
            f"🗄 База: <code>{database_name}</code>\n"
            f"📦 Размер: {size_str}, хранилищ: {len(resolved_storage_ids)}, время: {duration}с",
        )
        return {
            "status": "success",
            "file_path": dump_result.object_name,
            "checksum": dump_result.checksum,
        }
    except Exception as e:
        if histories:
            for history in histories:
                if history.status == "running":
                    history.status = "failed"
                    history.stage = "failed"
                    history.error_message = str(e)
                    history.finished_at = datetime.utcnow()
            session.commit()
            history_id = primary.id if primary else histories[0].id
        else:
            history_id = None

        server_name = server.name if 'server' in locals() and server else None
        if org_id is not None:
            _publish(org_id, "backup_failed", {
                "id": history_id, "task_id": task_id,
                "server_id": server_id, "server_name": server_name,
                "database": database_name, "error": str(e),
                "finished_at": datetime.utcnow().isoformat(),
            })
        if 'server' in locals() and server:
            fire_event_notifications(
                session, "backup_failed", server_id,
                f"❌ <b>Ошибка бэкапа</b>\n🖥 Сервер: <code>{server.name}</code>\n🗄 База: <code>{database_name}</code>\n📋 {str(e)[:200]}",
            )
        return {"status": "error", "error": str(e)}
    finally:
        if dump_result and os.path.exists(dump_result.tmp_path):
            os.unlink(dump_result.tmp_path)
        session.close()
        _release_lock(lock_key)


@celery.task(name="app.tasks.backup_tasks.run_restore_task", bind=True)
def run_restore_task(self, server_id: int, database_name: str, file_path: str,
                     backup_format: str = "custom", backup_id: int | None = None) -> dict:
    task_id = self.request.id
    session = _get_sync_session()
    server = session.get(Server, server_id)
    if not server:
        session.close()
        return {"status": "error", "error": "Server not found"}
    org_id = server.organization_id
    server_name = server.name
    session.close()

    # Запись истории (running) — ДО захвата лока, чтобы конкурирующий бэкап/restore
    # видел живое восстановление и не «украл» общий лок.
    session = _get_sync_session()
    rec = RestoreHistory(
        server_id=server_id, database_name=database_name, status="running",
        task_id=task_id, backup_id=backup_id, file_path=file_path,
        backup_format=backup_format,
    )
    session.add(rec)
    session.commit()
    rec_id = rec.id
    session.close()

    # Общий с бэкапами лок → backup и restore одной БД не идут параллельно.
    acquired, lock_key = _acquire_lock(server_id, database_name)
    if not acquired:
        msg = "По этой базе уже идёт бэкап или восстановление"
        _finish_restore(rec_id, "failed", msg, None)
        _publish(org_id, "restore_failed", {"task_id": task_id, "error": msg})
        return {"status": "error", "error": "busy"}

    _publish(org_id, "restore_started", {
        "task_id": task_id, "server_id": server_id,
        "server_name": server_name, "database": database_name,
    })

    def _on_progress(kind: str, data: dict):
        _publish(org_id, "restore_progress", {"task_id": task_id, "kind": kind, **data})

    t0 = time.time()
    try:
        run_pg_restore(server, database_name, file_path, server_id=server_id, backup_format=backup_format, on_progress=_on_progress)
        _finish_restore(rec_id, "success", None, int(time.time() - t0))
        _publish(org_id, "restore_completed", {
            "task_id": task_id, "server_name": server_name, "database": database_name,
        })
        return {"status": "success"}
    except Exception as e:
        import traceback
        detail = f"{type(e).__name__}: {e}"
        print(f"[restore] task {task_id} FAILED (server={server_name} db={database_name}): "
              f"{detail}\n{traceback.format_exc()}", flush=True)
        _finish_restore(rec_id, "failed", detail, int(time.time() - t0))
        _publish(org_id, "restore_failed", {"task_id": task_id, "error": detail})
        return {"status": "error", "error": detail}
    finally:
        _release_lock(lock_key)


@celery.task(name="app.tasks.backup_tasks.run_scheduled_backups", queue=PLATFORM_QUEUE)
def run_scheduled_backups() -> None:
    for org_id in list_organization_ids():
        enqueue_org_task(run_org_scheduled_backups, org_id, org_id)


@celery.task(name="app.tasks.backup_tasks.run_org_scheduled_backups")
def run_org_scheduled_backups(org_id: int) -> None:
    session = _get_sync_session()
    org_server_ids = list(
        session.execute(
            select(Server.id).where(Server.organization_id == org_id)
        ).scalars().all()
    )
    if not org_server_ids:
        session.close()
        return

    schedules = session.execute(
        select(BackupSchedule).where(
            BackupSchedule.is_active == True,
            BackupSchedule.server_id.in_(org_server_ids),
        )
    ).scalars().all()

    now = datetime.utcnow()
    for schedule in schedules:
        last = session.execute(
            select(BackupHistory)
            .where(BackupHistory.server_id == schedule.server_id)
            .where(BackupHistory.database_name == schedule.database_name)
            .order_by(BackupHistory.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        should_run = last is None or _should_run_cron(schedule.cron_expression, last.started_at, now)
        if should_run:
            server = session.get(Server, schedule.server_id)
            if not server or (server.health_status or "") == "offline":
                continue
            storage_ids = schedule.storage_ids
            if not storage_ids:
                if server.storage_id:
                    storage_ids = [server.storage_id]
            enqueue_org_task(
                run_backup_task, org_id,
                schedule.server_id, schedule.database_name, "custom",
                None, storage_ids,
            )

    session.close()


@celery.task(name="app.tasks.backup_tasks.cleanup_old_backups", queue=PLATFORM_QUEUE)
def cleanup_old_backups() -> None:
    for org_id in list_organization_ids():
        enqueue_org_task(cleanup_org_backups, org_id, org_id)


@celery.task(name="app.tasks.backup_tasks.cleanup_org_backups")
def cleanup_org_backups(org_id: int) -> None:
    session = _get_sync_session()
    org_server_ids = list(
        session.execute(
            select(Server.id).where(Server.organization_id == org_id)
        ).scalars().all()
    )
    if not org_server_ids:
        session.close()
        return

    schedules = session.execute(
        select(BackupSchedule).where(
            BackupSchedule.is_active == True,
            BackupSchedule.server_id.in_(org_server_ids),
        )
    ).scalars().all()

    now = datetime.utcnow()

    for schedule in schedules:
        all_backups = session.execute(
            select(BackupHistory)
            .where(BackupHistory.server_id == schedule.server_id)
            .where(BackupHistory.database_name == schedule.database_name)
            .where(BackupHistory.status == "success")
            .order_by(BackupHistory.started_at.desc())
        ).scalars().all()

        # Простая ретенция по возрасту: держим бэкапы моложе retention_days.
        # Самый свежий (all_backups[0], сортировка desc) не удаляем никогда —
        # чтобы не остаться без бэкапа, даже если он старше порога.
        cutoff = now - timedelta(days=schedule.retention_days)
        for idx, backup in enumerate(all_backups):
            if idx == 0:
                continue
            if backup.started_at >= cutoff:
                continue
            if backup.file_path:
                minio_service.delete_file(
                    schedule.server_id,
                    backup.file_path,
                    storage_id=backup.storage_id,
                )
            session.delete(backup)

    session.commit()
    session.close()


def _should_run_cron(cron_expr: str, last_run: datetime, now: datetime) -> bool:
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False

    minute, hour, dom, month, dow = parts

    if minute != "*" and now.minute != int(minute):
        return False
    if hour != "*" and now.hour != int(hour):
        return False

    diff = (now - last_run).total_seconds()
    min_interval = 60
    if hour != "*":
        min_interval = 3600
    return diff >= min_interval
