import asyncio
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery
from app.config import settings
from app.models.server import Server
from app.services.server_health_service import (
    apply_health_probe,
    format_recovered_message,
    format_unreachable_message,
    probe_server_health,
    HEALTH_OFFLINE,
    DEFAULT_OFFLINE_THRESHOLD,
)
from app.services.event_bus import org_events_channel
from app.tasks.notification_tasks import fire_event_notifications
from app.tasks.queues import PLATFORM_QUEUE, list_organization_ids, enqueue_org_task

import redis as sync_redis


def _get_sync_session() -> Session:
    engine = create_engine(settings.app_db_url_sync)
    return Session(engine)


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _offline_threshold_for_org(session: Session, org_id: int) -> int:
    from app.models.notification import AlertRule

    rule = session.execute(
        select(AlertRule).where(
            AlertRule.organization_id == org_id,
            AlertRule.rule_type == "server_unreachable",
            AlertRule.is_active.is_(True),
        )
    ).scalars().first()
    if not rule:
        return DEFAULT_OFFLINE_THRESHOLD
    try:
        data = json.loads(rule.threshold_json or "{}")
        value = int(data.get("fail_count", DEFAULT_OFFLINE_THRESHOLD))
        return max(1, value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return DEFAULT_OFFLINE_THRESHOLD


@celery.task(name="app.tasks.server_health_tasks.check_all_server_health", queue=PLATFORM_QUEUE)
def check_all_server_health() -> None:
    for org_id in list_organization_ids():
        enqueue_org_task(check_org_server_health, org_id, org_id)


@celery.task(name="app.tasks.server_health_tasks.check_org_server_health")
def check_org_server_health(org_id: int) -> None:
    session = _get_sync_session()
    threshold = _offline_threshold_for_org(session, org_id)
    servers = session.execute(
        select(Server).where(
            Server.organization_id == org_id,
            Server.is_active.is_(True),
        )
    ).scalars().all()

    r = sync_redis.from_url(settings.redis_url)
    channel = org_events_channel(org_id)

    try:
        for server in servers:
            # Сбой одного сервера не должен прерывать проверку остальных.
            try:
                prev_status = server.health_status
                try:
                    ok, _version, error, pg_major = _run_async(probe_server_health(server))
                except Exception as exc:  # noqa: BLE001
                    ok, error, pg_major = False, str(exc), None

                became_offline, recovered = apply_health_probe(
                    server, ok, error, pg_major, offline_threshold=threshold,
                )

                if became_offline:
                    fire_event_notifications(
                        session, "server_unreachable", server.id,
                        format_unreachable_message(server),
                    )
                elif recovered and prev_status == HEALTH_OFFLINE:
                    fire_event_notifications(
                        session, "server_recovered", server.id,
                        format_recovered_message(server),
                    )

                try:
                    r.publish(channel, json.dumps({
                        "type": "server_health_update",
                        "data": {
                            "server_id": server.id,
                            "health_status": server.health_status,
                            "health_error": server.health_error,
                            "health_fail_count": server.health_fail_count,
                            "health_checked_at": server.health_checked_at.isoformat()
                            if server.health_checked_at else None,
                        },
                    }))
                except Exception as e:  # noqa: BLE001
                    print(f"[health] WS-публикация для сервера {server.id} не удалась: {e}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[health] сервер {server.id} пропущен: {type(e).__name__}: {e}", flush=True)
                continue

        session.commit()
    finally:
        session.close()
        r.close()
