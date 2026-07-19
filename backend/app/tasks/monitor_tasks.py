import asyncio
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import redis as sync_redis

from app.tasks.celery_app import celery
from app.config import settings
from app.models.server import Server
from app.services.monitor_service import get_monitoring_snapshot, save_snapshot_to_redis
from app.services.event_bus import org_events_channel
from app.tasks.queues import PLATFORM_QUEUE, list_organization_ids, enqueue_org_task


def _get_sync_session() -> Session:
    engine = create_engine(settings.app_db_url_sync)
    return Session(engine)


@celery.task(name="app.tasks.monitor_tasks.collect_all_metrics", queue=PLATFORM_QUEUE)
def collect_all_metrics() -> None:
    for org_id in list_organization_ids():
        enqueue_org_task(collect_org_metrics, org_id, org_id)


@celery.task(name="app.tasks.monitor_tasks.collect_org_metrics")
def collect_org_metrics(org_id: int) -> None:
    session = _get_sync_session()
    servers = session.execute(
        select(Server).where(
            Server.organization_id == org_id,
            Server.is_active == True,
        )
    ).scalars().all()
    session.close()

    r = sync_redis.from_url(settings.redis_url)
    channel = org_events_channel(org_id)

    try:
        for server in servers:
            try:
                try:
                    snapshot = asyncio.get_event_loop().run_until_complete(
                        get_monitoring_snapshot(server)
                    )
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    snapshot = loop.run_until_complete(get_monitoring_snapshot(server))
                    loop.close()
            except Exception as e:  # noqa: BLE001
                print(f"[metrics] сервер {server.id} ({server.name}) не отдал метрики: "
                      f"{type(e).__name__}: {e}", flush=True)
                continue

            save_snapshot_to_redis(server.id, snapshot)
            r.publish(channel, json.dumps({
                "type": "metrics_update",
                "data": {"server_id": server.id, "server_name": server.name, **snapshot},
            }, default=str))
    finally:
        r.close()
