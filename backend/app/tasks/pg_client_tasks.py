from datetime import datetime

from app.tasks.celery_app import celery
from app.services import pg_client_service
from app.services.event_bus import publish_platform_event
from app.tasks.queues import PLATFORM_QUEUE


def _publish(event_type: str, data: dict) -> None:
    publish_platform_event(event_type, data)


def _progress(task_id: str, kind: str, **payload) -> None:
    _publish("pg_client_progress", {"task_id": task_id, "kind": kind, **payload})


@celery.task(name="app.tasks.pg_client_tasks.install_pg_client_task", bind=True, queue=PLATFORM_QUEUE)
def install_pg_client_task(self, major: int) -> dict:
    task_id = self.request.id

    def on_log(source: str, line: str) -> None:
        _progress(task_id, "log", source=source, line=line)

    def on_stage(stage: str, message: str | None = None) -> None:
        _progress(task_id, "stage", stage=stage, message=message)

    _publish("pg_client_started", {
        "task_id": task_id,
        "major": major,
        "action": "install",
    })

    try:
        result = pg_client_service.install_client(major, on_log=on_log, on_stage=on_stage)
    except Exception as e:  # noqa: BLE001 — любая ошибка → всегда публикуем failed
        result = {"ok": False, "message": f"{type(e).__name__}: {e}"}

    finished_at = datetime.utcnow().isoformat()
    if result.get("ok"):
        _publish("pg_client_completed", {
            "task_id": task_id,
            "major": major,
            "action": "install",
            "message": result.get("message"),
            "finished_at": finished_at,
        })
    else:
        _publish("pg_client_failed", {
            "task_id": task_id,
            "major": major,
            "action": "install",
            "error": result.get("message", "Ошибка установки"),
            "finished_at": finished_at,
        })
    return result


@celery.task(name="app.tasks.pg_client_tasks.uninstall_pg_client_task", bind=True, queue=PLATFORM_QUEUE)
def uninstall_pg_client_task(self, major: int) -> dict:
    task_id = self.request.id

    def on_log(source: str, line: str) -> None:
        _progress(task_id, "log", source=source, line=line)

    def on_stage(stage: str, message: str | None = None) -> None:
        _progress(task_id, "stage", stage=stage, message=message)

    _publish("pg_client_started", {
        "task_id": task_id,
        "major": major,
        "action": "uninstall",
    })

    try:
        result = pg_client_service.uninstall_client(major, on_log=on_log, on_stage=on_stage)
    except Exception as e:  # noqa: BLE001 — любая ошибка → всегда публикуем failed
        result = {"ok": False, "message": f"{type(e).__name__}: {e}"}

    finished_at = datetime.utcnow().isoformat()
    if result.get("ok"):
        _publish("pg_client_completed", {
            "task_id": task_id,
            "major": major,
            "action": "uninstall",
            "message": result.get("message"),
            "finished_at": finished_at,
        })
    else:
        _publish("pg_client_failed", {
            "task_id": task_id,
            "major": major,
            "action": "uninstall",
            "error": result.get("message", "Ошибка удаления"),
            "finished_at": finished_at,
        })
    return result


@celery.task(name="app.tasks.pg_client_tasks.refresh_pg_repo_task", bind=True, queue=PLATFORM_QUEUE)
def refresh_pg_repo_task(self) -> dict:
    task_id = self.request.id

    def on_log(source: str, line: str) -> None:
        _progress(task_id, "log", source=source, line=line)

    def on_stage(stage: str, message: str | None = None) -> None:
        _progress(task_id, "stage", stage=stage, message=message)

    _publish("pg_client_started", {
        "task_id": task_id,
        "major": None,
        "action": "refresh",
    })

    try:
        result = pg_client_service.list_available_clients(
            refresh=True,
            on_log=on_log,
            on_stage=on_stage,
        )
    except Exception as e:  # noqa: BLE001 — любая ошибка → всегда публикуем failed
        result = {"ok": False, "message": f"{type(e).__name__}: {e}", "packages": []}

    finished_at = datetime.utcnow().isoformat()
    if result.get("ok"):
        count = len(result.get("packages") or [])
        _publish("pg_client_completed", {
            "task_id": task_id,
            "major": None,
            "action": "refresh",
            "message": result.get("message") or f"Загружено {count} пакетов",
            "package_count": count,
            "finished_at": finished_at,
        })
    else:
        _publish("pg_client_failed", {
            "task_id": task_id,
            "major": None,
            "action": "refresh",
            "error": result.get("message", "Ошибка загрузки PGDG"),
            "finished_at": finished_at,
        })
    return result
