"""Celery-задачи для сценариев восстановления (prod → devprod и т.п.)."""
import json as _json
import os
import time
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery
from app.config import settings
from app.models.server import Server
from app.models.scenario import RestoreScenario, RestoreScenarioRun
from app.services.backup_service import create_pg_dump, restore_pg_dump_local, _unlink_quiet
from app.services.db_admin_service import (
    terminate_connections,
    database_exists,
    rename_database,
    drop_database,
    create_database,
    list_database_extensions,
    ensure_extensions,
    list_database_roles,
    ensure_roles,
)
from app.services.event_bus import publish_org_event
from app.tasks.notification_tasks import fire_event_notifications
from app.tasks.queues import PLATFORM_QUEUE, list_organization_ids, enqueue_org_task


# Persistent-каталог для дампов сценариев (том scenario_dumps в worker).
# Переживает пересоздание контейнера → уцелевший при провале дамп можно
# переиспользовать при повторе. Чистится: успех → удаляем; новый прогон →
# удаляем прежний; reaper → сироты и старше TTL.
SCENARIO_DUMP_DIR = os.environ.get("SCENARIO_DUMP_DIR", "/var/lib/pgadmin/scenario_dumps")
SCENARIO_DUMP_TTL_DAYS = 7


def _get_sync_session() -> Session:
    engine = create_engine(settings.app_db_url_sync)
    return Session(engine)


def _publish(org_id: int, event_type: str, data: dict) -> None:
    publish_org_event(org_id, event_type, data)


def _step(session: Session, run: RestoreScenarioRun, step: str, org_id: int) -> None:
    run.current_step = step
    session.commit()
    _publish(org_id, "scenario_step", {
        "task_id": run.task_id,
        "run_id": run.id,
        "scenario_id": run.scenario_id,
        "step": step,
    })


def _make_log_callback(task_id: str, run_id: int, scenario_id: int, org_id: int) -> callable:
    """Возвращает on_progress коллбэк, который публикует строки лога сценария."""
    def on_progress(kind: str, data: dict) -> None:
        if kind == "log":
            _publish(org_id, "scenario_log", {
                "task_id": task_id,
                "run_id": run_id,
                "scenario_id": scenario_id,
                "source": data.get("source", ""),
                "line": data.get("line", ""),
                "level": data.get("level", "log"),  # error → красным в UI сразу
            })
        elif kind in ("phase", "dump_bytes"):
            msg = data.get("message") or data.get("phase") or ""
            if kind == "dump_bytes":
                bytes_written = data.get("bytes_written", 0)
                _publish(org_id, "scenario_bytes", {
                    "task_id": task_id,
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "bytes_written": bytes_written,
                })
            elif msg:
                _publish(org_id, "scenario_log", {
                    "task_id": task_id,
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "source": "info",
                    "line": msg,
                })
    return on_progress


@celery.task(name="app.tasks.scenario_tasks.run_scenario_task", bind=True)
def run_scenario_task(self, scenario_id: int, reuse_dump: bool = False) -> dict:
    task_id = self.request.id
    session = _get_sync_session()

    scenario = session.get(RestoreScenario, scenario_id)
    if not scenario:
        session.close()
        return {"status": "error", "error": "Scenario not found"}

    org_id = scenario.organization_id
    if not org_id:
        source = session.get(Server, scenario.source_server_id)
        if source and source.organization_id:
            org_id = source.organization_id
            scenario.organization_id = org_id
            session.commit()

    run = RestoreScenarioRun(
        scenario_id=scenario_id,
        task_id=task_id,
        status="running",
        current_step="init",
        started_at=datetime.utcnow(),
    )
    session.add(run)
    session.commit()

    _publish(org_id, "scenario_started", {
        "task_id": task_id,
        "run_id": run.id,
        "scenario_id": scenario_id,
        "scenario_name": scenario.name,
        "source_server_id": scenario.source_server_id,
        "source_database": scenario.source_database,
        "target_database": scenario.target_database,
    })

    source_server = session.get(Server, scenario.source_server_id)
    target_server = session.get(Server, scenario.target_server_id)

    if not source_server or not target_server:
        _fail(session, run, "Сервер-источник или сервер-цель не найден")
        return {"status": "error", "error": "Server not found"}

    backup_path: str | None = None

    excluded_tables: list[str] = []
    try:
        excluded_tables = _json.loads(scenario.excluded_tables_json or "[]")
    except Exception:
        excluded_tables = []

    log_cb = _make_log_callback(task_id, run.id, scenario_id, org_id)

    dump = None
    dump_path: str | None = None      # путь к дампу, который используем для restore
    reused = False
    try:
        # ── Шаг 1: Снять бэкап ЛИБО переиспользовать дамп прошлого прогона ──
        _step(session, run, "backup_source", org_id)
        can_reuse = (
            reuse_dump
            and scenario.reuse_dump_path
            and os.path.exists(scenario.reuse_dump_path)
        )
        if can_reuse:
            reused = True
            dump_path = scenario.reuse_dump_path
            try:
                sz = scenario.reuse_dump_size or os.path.getsize(dump_path)
            except OSError:
                sz = 0
            run.backup_path = dump_path
            session.commit()
            _publish(org_id, "scenario_log", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "source": "info",
                "line": f"Переиспользован дамп прошлого прогона: {sz / 1024 / 1024:.1f} MB — шаг бэкапа пропущен",
            })
        else:
            # Свежий дамп в persistent-каталог. Прежний reuse-дамп удаляем (≤1 на сценарий).
            if scenario.reuse_dump_path:
                _unlink_quiet(scenario.reuse_dump_path)
                scenario.reuse_dump_path = None
                scenario.reuse_dump_size = None
                scenario.reuse_dump_at = None
                session.commit()
            dump = create_pg_dump(
                source_server,
                scenario.source_database,
                backup_format="custom",
                excluded_tables=excluded_tables,
                on_progress=log_cb,
                dest_dir=SCENARIO_DUMP_DIR,
            )
            dump_path = dump.tmp_path
            run.backup_path = dump.object_name
            # Привязываем дамп к сценарию СРАЗУ после снятия (не в except):
            # тогда даже если прогон убьют (redeploy / kill worker), дамп
            # останется reusable. При успехе — очистим ниже.
            scenario.reuse_dump_path = dump_path
            scenario.reuse_dump_size = dump.file_size
            scenario.reuse_dump_at = datetime.utcnow()
            session.commit()
            _publish(org_id, "scenario_log", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "source": "info",
                "line": f"Бэкап снят: {dump.file_size / 1024 / 1024:.1f} MB (локальный дамп, S3 не используется)",
            })

        # ── Шаг 2: Кикнуть все подключения к целевой БД ─────────────────
        _step(session, run, "terminate_connections", org_id)
        if database_exists(target_server, scenario.target_database):
            kicked = terminate_connections(target_server, scenario.target_database)
            _publish(org_id, "scenario_log", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "source": "info",
                "line": f"Завершено {kicked} подключений к {scenario.target_database}",
            })
            time.sleep(2)
        else:
            _publish(org_id, "scenario_log", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "source": "info",
                "line": f"БД {scenario.target_database} не существует — пропуск кика сессий",
            })

        # ── Шаг 3: Переименовать или удалить старую БД ──────────────────
        if database_exists(target_server, scenario.target_database):
            if scenario.old_db_action == "rename":
                _step(session, run, "rename_old_db", org_id)
                suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                new_name = f"{scenario.target_database}_old_{suffix}"
                rename_database(target_server, scenario.target_database, new_name)
                run.renamed_to = new_name
                session.commit()
                _publish(org_id, "scenario_log", {
                    "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                    "source": "info",
                    "line": f"ALTER DATABASE {scenario.target_database} RENAME TO {new_name}",
                })
            else:
                _step(session, run, "drop_old_db", org_id)
                drop_database(target_server, scenario.target_database)
                _publish(org_id, "scenario_log", {
                    "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                    "source": "info",
                    "line": f"DROP DATABASE {scenario.target_database}",
                })

        # ── Шаг 4: Создать чистую целевую БД ────────────────────────────
        _step(session, run, "create_target_db", org_id)
        create_database(target_server, scenario.target_database)
        _publish(org_id, "scenario_log", {
            "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
            "source": "info",
            "line": f"CREATE DATABASE {scenario.target_database}",
        })

        # ── Шаг 4.5: Подготовить окружение целевой БД (preflight) ────────
        # Частые причины падения restore на чужом сервере: не хватает расширений
        # (PostGIS → «type geometry does not exist») и/или ролей-владельцев/
        # грантополучателей («role X does not exist»). Свежая target (template0)
        # пуста — создаём нужное заранее из источника; если что-то создать нельзя,
        # падаем СРАЗУ с реальной причиной, а не каскадом ошибок в самом конце.
        _step(session, run, "prepare_extensions", org_id)

        def _log_info(line: str) -> None:
            _publish(org_id, "scenario_log", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "source": "info", "line": line,
            })

        problems: list[str] = []

        # Роли (владельцы/гранты) — должны существовать до восстановления объектов.
        source_roles = list_database_roles(source_server, scenario.source_database)
        if source_roles:
            role_res = ensure_roles(target_server, scenario.target_database, source_roles)
            for nm in role_res["created"]:
                _log_info(f"Роль создана на целевом сервере: {nm}")
            problems += [f"роль {f['name']} — {f['error']}" for f in role_res["failed"]]

        # Расширения (типы/функции: PostGIS и т.п.).
        source_exts = list_database_extensions(source_server, scenario.source_database)
        if source_exts:
            ext_res = ensure_extensions(target_server, scenario.target_database, source_exts)
            for nm in ext_res["created"]:
                _log_info(f"Расширение подготовлено: {nm}")
            problems += [f"расширение {f['name']} — {f['error']}" for f in ext_res["failed"]]

        if problems:
            raise RuntimeError(
                "Восстановление невозможно: не удалось подготовить окружение на целевом "
                f"сервере ({'; '.join(problems)}). Для расширений — установите их на "
                "целевом сервере (уровень ОС) и/или дайте права CREATE EXTENSION; для ролей "
                "— дайте пользователю право CREATE ROLE (или создайте роли заранее)."
            )

        # ── Шаг 5: Восстановить бэкап ────────────────────────────────────
        _step(session, run, "restore", org_id)
        restore_pg_dump_local(
            target_server,
            scenario.target_database,
            dump_path,
            backup_format="custom",
            on_progress=log_cb,
            clean=False,
        )

        # ── Завершено ────────────────────────────────────────────────────
        run.status = "success"
        run.current_step = "done"
        run.finished_at = datetime.utcnow()
        # Успех → дамп больше не нужен: удаляем файл и чистим reuse-поля сценария.
        if dump_path:
            _unlink_quiet(dump_path)
        scenario.reuse_dump_path = None
        scenario.reuse_dump_size = None
        scenario.reuse_dump_at = None
        session.commit()

        _publish(org_id, "scenario_completed", {
            "task_id": task_id,
            "run_id": run.id,
            "scenario_id": scenario_id,
            "scenario_name": scenario.name,
            "status": "success",
        })

        fire_event_notifications(
            session,
            "scenario_success",
            scenario.target_server_id,
            (
                f"✅ <b>Сценарий завершён: {scenario.name}</b>\n"
                f"🖥 {source_server.name}/{scenario.source_database}"
                f" → {target_server.name}/{scenario.target_database}\n"
                f"📋 Старая БД: {scenario.old_db_action}"
                + (f" → <code>{run.renamed_to}</code>" if run.renamed_to else "")
            ),
        )

        return {"status": "success", "run_id": run.id}

    except Exception as e:
        _fail(session, run, str(e))
        # Дамп уже привязан к сценарию (сразу после снятия) — при провале он
        # остаётся reusable. Здесь только подсказка в лог.
        if dump_path and os.path.exists(dump_path):
            _publish(org_id, "scenario_log", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "source": "info",
                "line": "Дамп сохранён — при повторе включи «Переиспользовать дамп», чтобы пропустить бэкап",
            })
        _publish(org_id, "scenario_failed", {
            "task_id": task_id,
            "run_id": run.id,
            "scenario_id": scenario_id,
            "scenario_name": scenario.name,
            "error": str(e),
        })
        fire_event_notifications(
            session,
            "scenario_failed",
            scenario.target_server_id if target_server else None,
            (
                f"❌ <b>Ошибка сценария: {scenario.name}</b>\n"
                f"Шаг: {run.current_step}\n"
                f"📋 {str(e)[:300]}"
            ),
        )
        return {"status": "error", "error": str(e)}
    finally:
        # Дамп НЕ удаляем безусловно: при успехе он уже удалён, при провале —
        # намеренно сохранён для повтора. Чистит его reaper/следующий прогон/успех.
        session.close()


@celery.task(name="app.tasks.scenario_tasks.cleanup_scenario_dumps")
def cleanup_scenario_dumps() -> dict:
    """Периодическая чистка каталога дампов сценариев:
    - привязанные к сценарию дампы старше TTL → удалить + очистить reuse-поля;
    - файлы-сироты (не привязаны — краш worker'а / удалённый сценарий) старше
      1 дня → удалить. Активные дампы (пишутся сейчас) не трогаем: у них свежий
      mtime, а порог сирот — сутки."""
    import glob
    if not os.path.isdir(SCENARIO_DUMP_DIR):
        return {"orphans": 0, "stale": 0}
    now = time.time()
    ttl_sec = SCENARIO_DUMP_TTL_DAYS * 86400
    removed_orphans = 0
    removed_stale = 0
    session = _get_sync_session()
    try:
        rows = session.execute(
            select(RestoreScenario).where(RestoreScenario.reuse_dump_path.isnot(None))
        ).scalars().all()
        referenced = {s.reuse_dump_path: s for s in rows if s.reuse_dump_path}

        for path, sc in referenced.items():
            try:
                if not os.path.exists(path):
                    sc.reuse_dump_path = None
                    sc.reuse_dump_size = None
                    sc.reuse_dump_at = None
                elif now - os.path.getmtime(path) > ttl_sec:
                    _unlink_quiet(path)
                    sc.reuse_dump_path = None
                    sc.reuse_dump_size = None
                    sc.reuse_dump_at = None
                    removed_stale += 1
            except OSError:
                pass
        session.commit()

        for f in glob.glob(os.path.join(SCENARIO_DUMP_DIR, "*")):
            if f in referenced:
                continue
            try:
                if now - os.path.getmtime(f) > 86400:
                    _unlink_quiet(f)
                    removed_orphans += 1
            except OSError:
                pass
        return {"orphans": removed_orphans, "stale": removed_stale}
    finally:
        session.close()


def _fail(session: Session, run: RestoreScenarioRun, message: str, step: str | None = None) -> None:
    run.status = "failed"
    step = step or run.current_step or "?"
    error_lines = [l for l in message.splitlines() if ": error:" in l.lower()]
    detail = "\n".join(error_lines) if error_lines else message
    run.error_message = f"[шаг: {step}] {detail}".strip()[:5000]
    run.finished_at = datetime.utcnow()
    try:
        session.commit()
    except Exception:  # noqa: BLE001
        try:
            session.rollback()
            session.commit()
        except Exception:  # noqa: BLE001
            print(f"[scenario] НЕ удалось записать failed для run {run.id}", flush=True)


_ORPHAN_MIN_AGE = timedelta(minutes=5)
_ORPHAN_HARD_AGE = timedelta(hours=6)


def _active_task_ids() -> set[str] | None:
    """task_id, реально выполняемые воркерами; None — воркеры не ответили."""
    try:
        replies = celery.control.inspect(timeout=5).active()
    except Exception:  # noqa: BLE001
        return None
    if not replies:
        return None
    ids: set[str] = set()
    for _w, tasks in replies.items():
        for t in (tasks or []):
            if t.get("id"):
                ids.add(t["id"])
    return ids


@celery.task(name="app.tasks.scenario_tasks.reap_orphaned_scenario_runs", queue=PLATFORM_QUEUE)
def reap_orphaned_scenario_runs() -> None:
    """Beat: гасит осиротевшие running/queued-сценарии (нет активной задачи Celery).
    Иначе сирота НАВСЕГДА блокирует запуск сценария (API отдаёт 409 'уже выполняется')."""
    session = _get_sync_session()
    try:
        active = _active_task_ids()
        now = datetime.utcnow()
        rows = session.execute(
            select(RestoreScenarioRun).where(
                RestoreScenarioRun.status.in_(("running", "queued"))
            )
        ).scalars().all()
        reaped = 0
        for run in rows:
            age = now - run.started_at
            if age < _ORPHAN_MIN_AGE:
                continue
            if active is not None:
                if run.task_id and run.task_id in active:
                    continue
                reason = ("Задача прервана: активной задачи Celery не найдено "
                          "(воркер перезапущен или недоступен).")
            else:
                if age < _ORPHAN_HARD_AGE:
                    continue
                reason = "Прогон висит слишком долго, Celery не отвечает — помечен failed."
            run.status = "failed"
            run.error_message = f"[шаг: {run.current_step or '?'}] {reason}"[:5000]
            run.finished_at = now
            reaped += 1
            sc = session.get(RestoreScenario, run.scenario_id)
            if sc and run.task_id:
                try:
                    publish_org_event(sc.organization_id, "scenario_failed", {
                        "task_id": run.task_id, "run_id": run.id, "error": reason,
                    })
                except Exception:  # noqa: BLE001
                    pass
        if reaped:
            session.commit()
            print(f"[scenario] реапнуто осиротевших сценариев: {reaped}", flush=True)
    finally:
        session.close()


@celery.task(name="app.tasks.scenario_tasks.run_scheduled_scenarios", queue=PLATFORM_QUEUE)
def run_scheduled_scenarios() -> None:
    for org_id in list_organization_ids():
        enqueue_org_task(run_org_scheduled_scenarios, org_id, org_id)


@celery.task(name="app.tasks.scenario_tasks.run_org_scheduled_scenarios")
def run_org_scheduled_scenarios(org_id: int) -> None:
    """Проверяет расписание сценариев организации и запускает те, у которых подошло время."""
    session = _get_sync_session()
    scenarios = session.execute(
        select(RestoreScenario).where(
            RestoreScenario.organization_id == org_id,
            RestoreScenario.is_active == True,
            RestoreScenario.cron_expression.isnot(None),
        )
    ).scalars().all()

    now = datetime.utcnow()

    for scenario in scenarios:
        last_run = session.execute(
            select(RestoreScenarioRun)
            .where(RestoreScenarioRun.scenario_id == scenario.id)
            .order_by(RestoreScenarioRun.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if _should_run_cron(scenario.cron_expression, last_run.started_at if last_run else None, now):
            # Не запускать по расписанию, если прошлый прогон ещё идёт — иначе два
            # параллельных DROP/CREATE по одной target-БД.
            if last_run and last_run.status in ("running", "queued"):
                continue
            source = session.get(Server, scenario.source_server_id)
            if source and (source.health_status or "") == "offline":
                continue
            enqueue_org_task(run_scenario_task, org_id, scenario.id)

    session.close()


def _should_run_cron(cron_expr: str, last_run: datetime | None, now: datetime) -> bool:
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False

    minute, hour, dom, month, dow = parts

    if minute != "*" and now.minute != int(minute):
        return False
    if hour != "*" and now.hour != int(hour):
        return False

    if last_run is None:
        return True

    min_interval = 60
    if hour != "*":
        min_interval = 3600
    return (now - last_run).total_seconds() >= min_interval
