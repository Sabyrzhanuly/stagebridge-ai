"""Celery-задачи сценария structure_sync — аддитивная миграция структуры.

Поток: backup test → клон prod в temp → накат структуры из test → данные новых
таблиц → проверка → (approval) → свап имён (temp → target, старый target → to_delete__).
Ничего на бою не удаляется до свапа; свап — за approval.
"""
import json as _json
import os
import traceback
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery
from app.config import settings
from app.models.server import Server
from app.models.structure_sync import StructureSyncScenario, StructureSyncRun
from app.services.backup_service import create_pg_dump, restore_pg_dump_local
from app.services.db_admin_service import (
    terminate_connections,
    database_exists,
    rename_database,
    drop_database,
    create_database,
    list_databases_with_prefix,
)
from app.services import schema_diff_service
from app.services.event_bus import publish_org_event
from app.tasks.notification_tasks import fire_event_notifications
from app.tasks.queues import PLATFORM_QUEUE, list_organization_ids, enqueue_org_task
from app.tasks.scenario_tasks import _should_run_cron


STALE_QUEUED_SECONDS = 300  # queued дольше — считаем не подхваченным воркером
ORPHAN_MIN_AGE = timedelta(minutes=5)   # running моложе не трогаем (мог не попасть в inspect)
ORPHAN_HARD_AGE = timedelta(hours=6)    # fallback, когда Celery inspect недоступен


def _get_sync_session() -> Session:
    engine = create_engine(settings.app_db_url_sync)
    return Session(engine)


def _reap_stale_queued(session: Session, scenario_id: int | None = None) -> int:
    """Помечает failed прогоны, зависшие в queued (воркер не подхватил).

    running не трогаем: длинные шаги (dump/restore) идут без коммита в БД и
    таймер убил бы живой прогон — для running есть ручной «Стоп».
    """
    stale_before = datetime.utcnow() - timedelta(seconds=STALE_QUEUED_SECONDS)
    q = select(StructureSyncRun).where(
        StructureSyncRun.status == "queued",
        StructureSyncRun.started_at < stale_before,
    )
    if scenario_id is not None:
        q = q.where(StructureSyncRun.scenario_id == scenario_id)
    rows = session.execute(q).scalars().all()
    for run in rows:
        run.status = "failed"
        run.error_message = "Задача не подхвачена воркером (таймаут очереди)"
        run.finished_at = datetime.utcnow()
    if rows:
        session.commit()
    return len(rows)


def _active_task_ids() -> set[str] | None:
    """task_id, реально выполняемые воркерами (Celery inspect active).
    None — воркеры не ответили (брокер молчит) → неопределённость, не реапим по active."""
    try:
        replies = celery.control.inspect(timeout=5).active()
    except Exception:  # noqa: BLE001
        return None
    if not replies:
        return None
    ids: set[str] = set()
    for _worker, tasks in replies.items():
        for t in (tasks or []):
            tid = t.get("id")
            if tid:
                ids.add(tid)
    return ids


def _reap_orphaned_running(session: Session, active_ids: set[str] | None) -> int:
    """Помечает failed прогоны в running, за которыми уже нет активной задачи Celery
    (воркер перезапущен/убит/недоступен). Живые прогоны в active_ids не трогаются."""
    now = datetime.utcnow()
    rows = session.execute(
        select(StructureSyncRun).where(StructureSyncRun.status == "running")
    ).scalars().all()
    reaped = 0
    for run in rows:
        age = now - run.started_at
        if age < ORPHAN_MIN_AGE:
            continue
        if active_ids is not None:
            if run.task_id and run.task_id in active_ids:
                continue  # задача жива
            reason = ("Задача прервана: активной задачи Celery не найдено "
                      "(воркер перезапущен или недоступен).")
        else:
            if age < ORPHAN_HARD_AGE:
                continue  # inspect недоступен — реапим только очень старые
            reason = ("Прогон висит в running слишком долго, Celery не отвечает — "
                      "помечен failed для безопасности.")
        run.status = "failed"
        run.error_message = f"[шаг: {run.current_step or '?'}] {reason}"[:5000]
        run.finished_at = now
        reaped += 1
        # убрать застывшую карточку из панели задач на фронте
        sc = session.get(StructureSyncScenario, run.scenario_id)
        if sc and run.task_id:
            try:
                publish_org_event(sc.organization_id, "structure_sync_failed", {
                    "task_id": run.task_id, "run_id": run.id,
                    "scenario_id": run.scenario_id, "error": reason,
                })
            except Exception:  # noqa: BLE001
                pass
    if reaped:
        session.commit()
        print(f"[structure_sync] реапнуто осиротевших running: {reaped}", flush=True)
    return reaped


def _publish(org_id: int, event_type: str, data: dict) -> None:
    publish_org_event(org_id, event_type, data)


def _step(session: Session, run: StructureSyncRun, step: str, org_id: int) -> None:
    run.current_step = step
    session.commit()
    _publish(org_id, "structure_sync_step", {
        "task_id": run.task_id,
        "run_id": run.id,
        "scenario_id": run.scenario_id,
        "step": step,
    })


def _log(org_id: int, run: StructureSyncRun, source: str, line: str, level: str = "log") -> None:
    _publish(org_id, "structure_sync_log", {
        "task_id": run.task_id,
        "run_id": run.id,
        "scenario_id": run.scenario_id,
        "source": source,
        "line": line,
        "level": level,  # error → красным в UI сразу
    })


def _make_log_cb(org_id: int, run: StructureSyncRun):
    def cb(kind: str, data: dict) -> None:
        if kind == "log":
            _log(org_id, run, data.get("source", ""), data.get("line", ""), data.get("level", "log"))
        elif kind == "phase":
            msg = data.get("message") or data.get("phase") or ""
            if msg:
                _log(org_id, run, "info", msg)
        elif kind == "dump_bytes":
            # Живой прогресс дампа (клон prod / safety-бэкап теста) — размер файла.
            _publish(org_id, "structure_sync_bytes", {
                "task_id": run.task_id,
                "run_id": run.id,
                "scenario_id": run.scenario_id,
                "bytes_written": data.get("bytes_written", 0),
            })
    return cb


def _temp_name(scenario: StructureSyncScenario) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    try:
        name = scenario.temp_name_template.format(target=scenario.target_name, ts=ts)
    except Exception:
        name = f"{scenario.target_name}_build_{ts}"
    return name[:63]


def _temp_prefix(scenario: StructureSyncScenario) -> str | None:
    """Стабильная часть имени temp до подстановки {ts} — для поиска осиротевших temp.

    Возвращает None, если префикс небезопасно широкий (нет {ts} или между target и
    ts нет статического разделителя): иначе чистка могла бы задеть боевые БД.
    """
    tmpl = scenario.temp_name_template or "{target}_build_{ts}"
    if "{ts}" not in tmpl:
        return None
    head = tmpl.split("{ts}")[0]
    try:
        prefix = head.format(target=scenario.target_name)
    except Exception:
        return None
    if not prefix or prefix == scenario.target_name or not prefix.endswith(("_", "-")):
        return None
    return prefix


def _cleanup_orphan_temps(session: Session, run: StructureSyncRun,
                          scenario: StructureSyncScenario, target_server: Server,
                          org_id: int, keep_temp_db: str) -> None:
    """Удаляет temp-БД от прерванных прогонов (по префиксу шаблона), кроме текущей.

    При terminate воркера finally не отрабатывает и temp остаётся на СЕРВЕРЕ-
    ПРИЁМНИКЕ; такие БД именуются по temp_name_template и НЕ подпадают под чистку
    to_delete__. Чистим при следующем прогоне, best-effort.
    """
    prefix = _temp_prefix(scenario)
    if not prefix:
        return
    try:
        candidates = list_databases_with_prefix(target_server, prefix)
    except Exception:  # noqa: BLE001
        return
    for db_name in candidates:
        if db_name in (keep_temp_db, scenario.target_name):
            continue
        try:
            terminate_connections(target_server, db_name)
            drop_database(target_server, db_name)
            _log(org_id, run, "info", f"Убрана осиротевшая temp: {db_name}")
        except Exception as e:  # noqa: BLE001
            _log(org_id, run, "info", f"Не удалось убрать temp {db_name}: {e}")


def _fail(session: Session, run: StructureSyncRun, message: str, step: str | None = None) -> None:
    """Помечает прогон failed, всегда сохраняя шаг и причину. Commit защищён —
    даже при проблемах с БД пытаемся записать статус, чтобы прогон не завис в running."""
    run.status = "failed"
    step = step or run.current_step or "?"
    # pg-ошибки (: error:) выделяем, но если их нет — сохраняем полное сообщение,
    # чтобы точная причина не терялась.
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
            print(f"[structure_sync] НЕ удалось записать failed для run {run.id}", flush=True)


@celery.task(name="app.tasks.structure_sync_tasks.run_structure_sync_task", bind=True)
def run_structure_sync_task(self, scenario_id: int, run_id: int | None = None, dry_run: bool = False) -> dict:
    task_id = self.request.id
    session = _get_sync_session()

    scenario = session.get(StructureSyncScenario, scenario_id)
    if not scenario:
        session.close()
        return {"status": "error", "error": "Scenario not found"}

    org_id = scenario.organization_id

    if run_id is not None:
        # Строка создана синхронно в API (run_now) — двойной запуск ловится там же.
        # Здесь только переводим queued → running и привязываем task_id.
        run = session.get(StructureSyncRun, run_id)
        if not run:
            session.close()
            return {"status": "error", "error": "Run not found"}
        if run.status != "queued":
            # Отменён (stop → failed) или уже обрабатывается — не выполняем повторно
            # (защита от stop в микроокне до task_id и от retry после worker-lost).
            session.close()
            return {"status": "skipped", "reason": f"run status={run.status}"}
        run.task_id = task_id
        run.status = "running"
        run.current_step = "init"
        session.commit()
    else:
        # Плановый (cron) запуск — строки ещё нет, создаём здесь.
        run = StructureSyncRun(
            scenario_id=scenario_id,
            task_id=task_id,
            status="running",
            current_step="init",
            dry_run=False,
            dropped_old_json="[]",
            started_at=datetime.utcnow(),
        )
        session.add(run)
        session.commit()

    _publish(org_id, "structure_sync_started", {
        "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
        "scenario_name": scenario.name,
    })

    prod_server = session.get(Server, scenario.prod_server_id)
    test_server = session.get(Server, scenario.test_server_id)
    # Приёмник: где собираем temp и делаем свап. Прод только читаем (pg_dump).
    target_server = session.get(Server, scenario.target_server_id)
    if not prod_server or not test_server or not target_server:
        _fail(session, run, "Сервер prod, test или приёмник не найден")
        session.close()
        return {"status": "error", "error": "Server not found"}

    log_cb = _make_log_cb(org_id, run)
    is_dry = bool(dry_run)
    run.dry_run = is_dry
    session.commit()

    temp_dump = None
    try:
        # ── Шаг 1: snapshot структуры теста (schema-only; best-effort; на dry-run пропускаем) ──
        # Только структура — данные теста в миграции не нужны (структуру читаем из
        # каталогов, данные новых таблиц копируем отдельно). Быстро на любой БД.
        if not is_dry:
            _step(session, run, "backup_test", org_id)
            try:
                safety = create_pg_dump(test_server, scenario.test_database,
                                        backup_format="custom", schema_only=True,
                                        on_progress=log_cb)
                _log(org_id, run, "info",
                     f"Снимок структуры теста (schema-only): {safety.file_size / 1024 / 1024:.1f} MB")
            except Exception as e:  # noqa: BLE001
                _log(org_id, run, "info", f"Снимок структуры теста пропущен: {e}")

        # ── Dry-run: дифф test vs prod напрямую, без клона и изменений ──
        if is_dry:
            _step(session, run, "dry_run_diff", org_id)
            plan = schema_diff_service.build_plan(
                test_server, scenario.test_database, prod_server, scenario.prod_database
            )
            run.summary_json = _json.dumps(plan.summary(), ensure_ascii=False)
            run.generated_sql = plan.as_sql()
            run.status = "dry_run"
            run.current_step = "done"
            run.finished_at = datetime.utcnow()
            session.commit()
            _publish(org_id, "structure_sync_completed", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "status": "dry_run",
            })
            return {"status": "dry_run", "run_id": run.id}

        # ── Шаг 2: клон prod → temp ──
        temp_db = _temp_name(scenario)
        run.temp_db = temp_db
        session.commit()
        _step(session, run, "clone_prod", org_id)
        # Размер prod для прогресса «по весу» (процент дампа). Best-effort.
        try:
            from app.services.backup_service import get_db_size
            _prod_size = get_db_size(prod_server, scenario.prod_database)
            if _prod_size:
                _publish(org_id, "structure_sync_total", {
                    "task_id": run.task_id,
                    "run_id": run.id,
                    "scenario_id": run.scenario_id,
                    "total_bytes": _prod_size,
                })
        except Exception:  # noqa: BLE001
            pass
        _cleanup_orphan_temps(session, run, scenario, target_server, org_id, temp_db)
        if database_exists(target_server, temp_db):
            drop_database(target_server, temp_db)
        excluded = _json.loads(scenario.excluded_tables_json or "[]")
        if excluded:
            _log(org_id, run, "info",
                 f"Клон без данных таблиц (структура сохранится): {', '.join(excluded)}")
        temp_dump = create_pg_dump(prod_server, scenario.prod_database,
                                   backup_format="custom", excluded_tables=excluded,
                                   on_progress=log_cb)
        create_database(target_server, temp_db)
        restore_pg_dump_local(target_server, temp_db, temp_dump.tmp_path,
                              backup_format="custom", on_progress=log_cb, clean=False)
        _log(org_id, run, "info", f"temp собрана как копия prod: {temp_db}")

        # ── Шаг 3: план аддитивных изменений ──
        _step(session, run, "build_plan", org_id)
        plan = schema_diff_service.build_plan(
            test_server, scenario.test_database, target_server, temp_db
        )
        run.generated_sql = plan.as_sql()
        session.commit()
        _log(org_id, run, "info", f"План: {plan.summary()}")

        all_errors: list[str] = []

        # ── Шаг 4: накат структуры (порядок: схемы → типы → таблицы → колонки → mv → func → view → trg) ──
        _step(session, run, "apply_schemas", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.schema_ddl, log_cb, "schemas")
        all_errors += errs

        _step(session, run, "apply_collations", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.collation_ddl, log_cb, "collations")
        all_errors += errs

        _step(session, run, "apply_extensions", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.extension_ddl, log_cb, "extensions")
        all_errors += errs

        _step(session, run, "apply_foreign", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.fdw_ddl + plan.server_ddl + plan.usermapping_ddl, log_cb, "foreign")
        all_errors += errs

        _step(session, run, "apply_types", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.type_ddl, log_cb, "types")
        all_errors += errs

        # Функции — РАННИЙ проход (check_function_bodies=off, тела не валидируются),
        # чтобы агрегаты / таблицы / индексы / constraints / generated-колонки могли
        # ссылаться на них. Ошибки НЕ учитываем — финальный apply_functions ниже
        # переприменит идемпотентно (CREATE OR REPLACE) и отчитается по-настоящему.
        if plan.function_ddl:
            _step(session, run, "apply_functions_early", org_id)
            schema_diff_service.apply_statements(
                target_server, temp_db,
                ["SET check_function_bodies = off", *plan.function_ddl],
                log_cb, "functions(pre)")

        _step(session, run, "apply_sequences", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.sequence_ddl, log_cb, "sequences")
        all_errors += errs

        _step(session, run, "apply_aggregates", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.aggregate_ddl, log_cb, "aggregates")
        all_errors += errs

        _step(session, run, "apply_new_tables", org_id)
        schema_diff_service.copy_tables(
            test_server, scenario.test_database, target_server, temp_db,
            plan.new_tables, include_data=(scenario.data_copy_mode == "new_tables_only"),
            on_progress=log_cb,
        )

        _step(session, run, "apply_columns", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.column_alters, log_cb, "columns")
        all_errors += errs

        _step(session, run, "apply_indexes", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.index_ddl, log_cb, "indexes")
        all_errors += errs

        _step(session, run, "apply_constraints", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.constraint_ddl, log_cb, "constraints")
        all_errors += errs

        _step(session, run, "apply_rls", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.rls_ddl, log_cb, "rls")
        all_errors += errs

        _step(session, run, "apply_matviews", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.matview_ddl, log_cb, "matviews")
        all_errors += errs

        _step(session, run, "apply_functions", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.function_ddl, log_cb, "functions")
        all_errors += errs

        _step(session, run, "apply_operators", org_id)
        _, errs = schema_diff_service.apply_statements(
            target_server, temp_db,
            plan.operator_ddl + plan.cast_ddl + plan.textsearch_ddl, log_cb, "operators/casts/ts")
        all_errors += errs

        _step(session, run, "apply_views", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.view_ddl, log_cb, "views")
        all_errors += errs

        _step(session, run, "apply_triggers", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.trigger_ddl, log_cb, "triggers")
        all_errors += errs

        _step(session, run, "apply_rules", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.rule_ddl, log_cb, "rules")
        all_errors += errs

        _step(session, run, "apply_event_triggers", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.event_trigger_ddl, log_cb, "event_triggers")
        all_errors += errs

        _step(session, run, "apply_publications", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.publication_ddl, log_cb, "publications")
        all_errors += errs

        _step(session, run, "apply_comments", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.comment_ddl, log_cb, "comments")
        all_errors += errs

        # Привилегии — последними, когда все объекты уже созданы.
        _step(session, run, "apply_grants", org_id)
        _, errs = schema_diff_service.apply_statements(target_server, temp_db, plan.grant_ddl, log_cb, "grants")
        all_errors += errs

        # ── Шаг 5: проверка ──
        _step(session, run, "verify", org_id)
        verify = _verify(test_server, scenario.test_database, target_server, temp_db, plan)
        summary = plan.summary()
        summary["apply_errors"] = all_errors[:100]
        summary["verify"] = verify
        run.summary_json = _json.dumps(summary, ensure_ascii=False)
        session.commit()

        if all_errors:
            print(f"[structure_sync] run {run.id}: {len(all_errors)} ошибок применения:\n"
                  + "\n".join(all_errors[:100]), flush=True)

        if verify.get("missing_tables"):
            _fail(session, run,
                  f"Проверка не прошла: в temp нет таблиц {verify['missing_tables']}", step="verify")
            _notify_failed(session, scenario, prod_server, run)
            return {"status": "error", "error": "verify failed"}

        # ── Шаг 6: approval / swap ──
        # Свап держим на подтверждении, если он так настроен ИЛИ были ошибки применения —
        # чтобы флаг «есть ошибки» никогда не свапился молча в авто-режиме.
        if scenario.require_approval or all_errors:
            run.status = "awaiting_approval"
            run.current_step = "awaiting_approval"
            if all_errors:
                run.error_message = (
                    f"{len(all_errors)} ошибок применения — свап на подтверждении. "
                    "Первые: " + " | ".join(all_errors[:5])
                )[:5000]
            session.commit()
            _publish(org_id, "structure_sync_awaiting_approval", {
                "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
                "temp_db": temp_db, "apply_errors": len(all_errors),
            })
            warn = (f"⚠️ <b>{len(all_errors)} ошибок применения</b> — проверьте перед свапом\n"
                    if all_errors else "")
            _notify(session, scenario, prod_server,
                    f"⏳ <b>structure_sync ждёт подтверждения: {scenario.name}</b>\n"
                    f"{warn}temp собрана: <code>{temp_db}</code>\nПодтвердите свап в UI.")
            return {"status": "awaiting_approval", "run_id": run.id, "apply_errors": len(all_errors)}

        _do_swap(session, run, scenario, target_server, org_id)
        return {"status": "success", "run_id": run.id}

    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        detail = f"{type(e).__name__}: {e}"
        step = run.current_step
        _fail(session, run, f"{detail}\n{tb}", step=step)
        print(f"[structure_sync] run {run.id} FAILED at step={step}: {detail}\n{tb}", flush=True)
        _publish(org_id, "structure_sync_failed", {
            "task_id": task_id, "run_id": run.id, "scenario_id": scenario_id,
            "error": detail,
        })
        _notify_failed(session, scenario, prod_server, run)
        return {"status": "error", "error": detail}
    finally:
        if temp_dump is not None and os.path.exists(temp_dump.tmp_path):
            os.unlink(temp_dump.tmp_path)
        session.close()


@celery.task(name="app.tasks.structure_sync_tasks.run_structure_sync_swap_task", bind=True)
def run_structure_sync_swap_task(self, run_id: int) -> dict:
    """Выполняет отложенный свап после подтверждения (approval)."""
    session = _get_sync_session()
    run = session.get(StructureSyncRun, run_id)
    if not run:
        session.close()
        return {"status": "error", "error": "Run not found"}
    if run.status != "running":
        # approve атомарно перевёл awaiting_approval → running; иное состояние
        # значит второй approve / отмена / повторный запуск — свап не выполняем.
        session.close()
        return {"status": "error", "error": "Run is not approved for swap"}

    scenario = session.get(StructureSyncScenario, run.scenario_id)
    # Свап целиком на приёмнике — резолвим target_server, а не prod.
    target_server = session.get(Server, scenario.target_server_id) if scenario else None
    if not scenario or not target_server:
        _fail(session, run, "Сценарий или сервер-приёмник не найден")
        session.close()
        return {"status": "error", "error": "not found"}

    run.status = "running"
    run.task_id = self.request.id
    session.commit()
    try:
        _do_swap(session, run, scenario, target_server, scenario.organization_id)
        return {"status": "success", "run_id": run.id}
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        detail = f"{type(e).__name__}: {e}"
        _fail(session, run, f"{detail}\n{tb}", step="swap")
        print(f"[structure_sync] SWAP run {run.id} FAILED: {detail}\n{tb}", flush=True)
        _notify_failed(session, scenario, target_server, run)
        return {"status": "error", "error": detail}
    finally:
        session.close()


def _do_swap(session: Session, run: StructureSyncRun, scenario: StructureSyncScenario,
             target_server: Server, org_id: int) -> None:
    # ВСЁ на сервере-приёмнике (target_server). Прод здесь вообще не участвует.
    target = scenario.target_name
    temp_db = run.temp_db
    prefix = scenario.old_db_prefix

    _step(session, run, "swap", org_id)
    terminate_connections(target_server, target)

    if database_exists(target_server, target):
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        renamed = f"{prefix}{target}_{ts}"[:63]
        rename_database(target_server, target, renamed)
        run.renamed_prod_to = renamed
        session.commit()
        _log(org_id, run, "info", f"ALTER DATABASE {target} RENAME TO {renamed}")

    rename_database(target_server, temp_db, target)
    _log(org_id, run, "info", f"ALTER DATABASE {temp_db} RENAME TO {target}")

    # чистка старых to_delete__{target}_*: держим keep_old_count + текущий
    dropped: list[str] = []
    candidates = list_databases_with_prefix(target_server, f"{prefix}{target}_")
    candidates.sort(reverse=True)  # новее — раньше (ts в имени)
    keep = scenario.keep_old_count + 1
    for old in candidates[keep:]:
        drop_database(target_server, old)
        dropped.append(old)
        _log(org_id, run, "info", f"DROP DATABASE {old}")
    run.dropped_old_json = _json.dumps(dropped, ensure_ascii=False)

    run.status = "success"
    run.current_step = "done"
    run.finished_at = datetime.utcnow()
    session.commit()

    _publish(org_id, "structure_sync_completed", {
        "task_id": run.task_id, "run_id": run.id, "scenario_id": scenario.id,
        "status": "success",
    })
    _notify(session, scenario, target_server,
            f"✅ <b>structure_sync завершён: {scenario.name}</b>\n"
            f"🖥 {target} обновлён на приёмнике (temp {temp_db} → {target})\n"
            + (f"📋 Старая БД приёмника: <code>{run.renamed_prod_to}</code>\n" if run.renamed_prod_to else "")
            + (f"🗑 Удалено старых: {len(dropped)}" if dropped else ""))


def _verify(test_server: Server, test_db: str, temp_server: Server, temp_db: str,
            plan: schema_diff_service.SyncPlan) -> dict:
    """Аддитивная проверка: все таблицы test присутствуют в temp; row-count новых таблиц."""
    _c = schema_diff_service._connect(temp_server, temp_db)
    try:
        temp_tables = set(schema_diff_service._tableish(_c, "'r','p','f'"))
    finally:
        _c.close()
    missing = [t for t in plan.new_tables if t not in temp_tables]
    row_checks = []
    for t in plan.new_tables:
        if t in missing:
            continue
        src = schema_diff_service.count_rows(test_server, test_db, t)
        dst = schema_diff_service.count_rows(temp_server, temp_db, t)
        row_checks.append({"table": t, "test": src, "temp": dst, "ok": src == dst})
    return {"missing_tables": missing, "row_checks": row_checks}


def _notify(session: Session, scenario: StructureSyncScenario, prod_server: Server, message: str) -> None:
    try:
        fire_event_notifications(session, "structure_sync_success",
                                 scenario.prod_server_id, message)
    except Exception as e:  # noqa: BLE001
        print(f"[structure_sync] уведомление (success) не отправлено: {e}", flush=True)


def _notify_failed(session: Session, scenario: StructureSyncScenario,
                   prod_server: Server | None, run: StructureSyncRun) -> None:
    try:
        fire_event_notifications(
            session, "structure_sync_failed",
            scenario.prod_server_id if scenario else None,
            f"❌ <b>Ошибка structure_sync: {scenario.name if scenario else '?'}</b>\n"
            f"Шаг: {run.current_step}\n📋 {(run.error_message or '')[:300]}",
        )
    except Exception as e:  # noqa: BLE001
        print(f"[structure_sync] уведомление (failed) не отправлено: {e}", flush=True)


# ─────────────────────────── расписание ──────────────────────────────

@celery.task(name="app.tasks.structure_sync_tasks.reap_stale_structure_sync_runs", queue=PLATFORM_QUEUE)
def reap_stale_structure_sync_runs() -> None:
    """Beat: гасит зависшие queued И осиротевшие running (без активной задачи Celery)."""
    session = _get_sync_session()
    try:
        _reap_stale_queued(session)
        _reap_orphaned_running(session, _active_task_ids())
    finally:
        session.close()


@celery.task(name="app.tasks.structure_sync_tasks.run_scheduled_structure_syncs", queue=PLATFORM_QUEUE)
def run_scheduled_structure_syncs() -> None:
    for org_id in list_organization_ids():
        enqueue_org_task(run_org_scheduled_structure_syncs, org_id, org_id)


@celery.task(name="app.tasks.structure_sync_tasks.run_org_scheduled_structure_syncs")
def run_org_scheduled_structure_syncs(org_id: int) -> None:
    session = _get_sync_session()
    try:
        scenarios = session.execute(
            select(StructureSyncScenario).where(
                StructureSyncScenario.organization_id == org_id,
                StructureSyncScenario.is_active == True,  # noqa: E712
                StructureSyncScenario.cron_expression.isnot(None),
            )
        ).scalars().all()

        now = datetime.utcnow()
        for scenario in scenarios:
            last_run = session.execute(
                select(StructureSyncRun)
                .where(StructureSyncRun.scenario_id == scenario.id)
                .order_by(StructureSyncRun.started_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if _should_run_cron(scenario.cron_expression, last_run.started_at if last_run else None, now):
                enqueue_org_task(run_structure_sync_task, org_id, scenario.id)
    finally:
        session.close()
