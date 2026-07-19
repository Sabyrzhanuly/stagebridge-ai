import asyncio
import json
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import redis as sync_redis

from app.tasks.celery_app import celery
from app.config import settings
from app.models.notification import AlertRule, NotificationChannel, NotificationHistory
from app.models.server import Server
from app.services.notification_service import send_notification
from app.services import smtp_settings_service
from app.tasks.queues import PLATFORM_QUEUE, list_organization_ids, enqueue_org_task

MONITORING_RULE_TYPES = {"max_connections", "long_query", "locks", "cache_hit_ratio", "database_size_gb"}


def _get_sync_session() -> Session:
    engine = create_engine(settings.app_db_url_sync)
    return Session(engine)


def _send_via_channel(session: Session, channel: NotificationChannel, rule_id: int | None, message: str) -> None:
    loop = asyncio.new_event_loop()
    ok = False
    try:
        smtp = None
        if channel.channel_type == "email":
            try:
                cfg = json.loads(channel.config_json)
            except json.JSONDecodeError:
                cfg = {}
            smtp = smtp_settings_service.smtp_from_channel_config(cfg)
        result = loop.run_until_complete(
            send_notification(
                channel.channel_type,
                channel.config_json,
                message,
                smtp=smtp,
            )
        )
        ok = result.ok
    except Exception as e:  # noqa: BLE001 — не молчим: причину в лог
        print(f"[notify] отправка в канал {channel.id} ({channel.channel_type}) не удалась: "
              f"{type(e).__name__}: {e}", flush=True)
    finally:
        loop.close()  # закрываем цикл ВСЕГДА (иначе утечка event loop при каждом сбое)
    history = NotificationHistory(
        channel_id=channel.id,
        rule_id=rule_id,
        message=message,
        status="sent" if ok else "failed",
        sent_at=datetime.utcnow(),
    )
    session.add(history)


def fire_event_notifications(session: Session, event_type: str, server_id: int | None, message: str) -> None:
    """Отправляет уведомления по активным правилам с данным event_type для указанного сервера.

    Правило срабатывает если его server_id совпадает с переданным или равно NULL (все серверы).
    """
    rules = session.execute(
        select(AlertRule).where(
            AlertRule.is_active == True,
            AlertRule.rule_type == event_type,
        )
    ).scalars().all()

    for rule in rules:
        if rule.server_id is not None and rule.server_id != server_id:
            continue
        channel = session.get(NotificationChannel, rule.channel_id)
        if not channel or not channel.is_active:
            continue
        _send_via_channel(session, channel, rule.id, message)

    session.commit()


@celery.task(name="app.tasks.notification_tasks.check_alert_rules", queue=PLATFORM_QUEUE)
def check_alert_rules() -> None:
    for org_id in list_organization_ids():
        enqueue_org_task(check_org_alert_rules, org_id, org_id)


@celery.task(name="app.tasks.notification_tasks.check_org_alert_rules")
def check_org_alert_rules(org_id: int) -> None:
    session = _get_sync_session()
    r = sync_redis.from_url(settings.redis_url)
    try:
        rules = session.execute(
            select(AlertRule).where(
                AlertRule.is_active == True,
                AlertRule.organization_id == org_id,
                AlertRule.rule_type.in_(MONITORING_RULE_TYPES),
            )
        ).scalars().all()

        for rule in rules:
            # Одно битое правило (кривой threshold_json / метрики) НЕ должно ронять
            # весь проход алертов организации.
            try:
                threshold = json.loads(rule.threshold_json or "{}")
                if rule.server_id:
                    server_ids = [rule.server_id]
                else:
                    rows = session.execute(
                        select(Server.id).where(
                            Server.is_active.is_(True),
                            Server.organization_id == org_id,
                        )
                    )
                    server_ids = [row[0] for row in rows.all()]

                for sid in server_ids:
                    raw = r.get(f"pgadmin:metrics:{sid}")
                    if not raw:
                        continue
                    try:
                        metrics = json.loads(raw)
                    except Exception:  # noqa: BLE001
                        continue
                    message = _evaluate_rule(rule.rule_type, threshold, metrics, sid)
                    if message:
                        channel = session.get(NotificationChannel, rule.channel_id)
                        if not channel or not channel.is_active:
                            continue
                        _send_via_channel(session, channel, rule.id, message)
            except Exception as e:  # noqa: BLE001
                print(f"[alert] правило {rule.id} пропущено: {type(e).__name__}: {e}", flush=True)
                continue

        session.commit()
    finally:
        session.close()
        r.close()


def _evaluate_rule(rule_type: str, threshold: dict, metrics: dict, server_id: int | None = None) -> str | None:
    server_tag = f" (server_id={server_id})" if server_id else ""

    if rule_type == "max_connections":
        total = metrics.get("connections", {}).get("total", 0)
        limit = threshold.get("max", 100)
        if total >= limit:
            return f"⚠️ <b>Превышение подключений</b>{server_tag}\nПодключений: <b>{total}</b>, лимит: {limit}"

    elif rule_type == "long_query":
        max_sec = threshold.get("max_seconds", 300)
        for q in metrics.get("slow_queries", []):
            if q.get("mean_time_ms", 0) / 1000 > max_sec:
                return (
                    f"🐢 <b>Медленный запрос</b>{server_tag}\n"
                    f"<code>{q['query'][:120]}</code>\n"
                    f"Среднее время: {q['mean_time_ms']:.0f}ms (лимит: {max_sec}s)"
                )

    elif rule_type == "locks":
        max_locks = threshold.get("max", 5)
        lock_count = len(metrics.get("locks", []))
        if lock_count >= max_locks:
            return f"🔒 <b>Блокировки</b>{server_tag}\nОжидающих блокировок: <b>{lock_count}</b> (лимит: {max_locks})"

    elif rule_type == "cache_hit_ratio":
        min_ratio = threshold.get("min", 90)
        ratio = metrics.get("cache_hit_ratio")
        if ratio is not None and ratio < min_ratio:
            return f"📉 <b>Низкий cache hit ratio</b>{server_tag}\nТекущий: <b>{ratio:.1f}%</b> (минимум: {min_ratio}%)"

    elif rule_type == "database_size_gb":
        max_gb = threshold.get("max_gb", 100)
        storage = metrics.get("storage") or {}
        total_bytes = int(storage.get("total_db_bytes") or 0)
        limit_bytes = int(max_gb * 1024 * 1024 * 1024)
        if total_bytes >= limit_bytes:
            total_gb = total_bytes / (1024 ** 3)
            return (
                f"💾 <b>Размер данных PostgreSQL</b>{server_tag}\n"
                f"Суммарный размер БД: <b>{total_gb:.1f} GB</b> (лимит: {max_gb} GB)\n"
                f"Это размер данных PG, не свободное место на диске ОС."
            )

    return None
