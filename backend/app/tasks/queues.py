"""Per-organization Celery queues (RabbitMQ) — имя очереди: org-{slug}."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

PLATFORM_QUEUE = "platform"
ORG_QUEUE_PREFIX = "org-"
LEGACY_ORG_QUEUE_RE = re.compile(r"^org_\d+$|^org_None$")
RABBITMQ_MGMT_URL = "http://rabbitmq:15672/api"


def org_queue_name(slug: str) -> str:
    return f"{ORG_QUEUE_PREFIX}{slug}"


def org_queue(org_id: int) -> str:
    """Имя очереди по organization_id (через slug)."""
    return org_queue_for_id(org_id)


def org_queue_for_id(org_id: int) -> str:
    slug = _load_slug(org_id)
    if not slug:
        raise ValueError(f"organization #{org_id} not found")
    return org_queue_name(slug)


def list_organization_slugs() -> list[str]:
    from app.models.organization import Organization

    engine = create_engine(settings.app_db_url_sync)
    try:
        with Session(engine) as session:
            return list(
                session.execute(
                    select(Organization.slug).order_by(Organization.slug)
                ).scalars().all()
            )
    finally:
        engine.dispose()


def list_organization_ids() -> list[int]:
    from app.models.organization import Organization

    engine = create_engine(settings.app_db_url_sync)
    try:
        with Session(engine) as session:
            return list(
                session.execute(
                    select(Organization.id).order_by(Organization.id)
                ).scalars().all()
            )
    finally:
        engine.dispose()


def list_worker_queues() -> list[str]:
    return [PLATFORM_QUEUE, *[org_queue_name(slug) for slug in list_organization_slugs()]]


def enqueue_org_task(task, org_id: int | None, *args, **kwargs):
    if org_id is None:
        raise ValueError(
            "organization_id обязателен: без него задача не попадёт в очередь организации"
        )
    return task.apply_async(args=args, kwargs=kwargs, queue=org_queue_for_id(org_id))


def enqueue_platform_task(task, *args, **kwargs):
    return task.apply_async(args=args, kwargs=kwargs, queue=PLATFORM_QUEUE)


def _load_slug(org_id: int) -> str | None:
    from app.models.organization import Organization

    engine = create_engine(settings.app_db_url_sync)
    try:
        with Session(engine) as session:
            org = session.get(Organization, org_id)
            return org.slug if org else None
    finally:
        engine.dispose()


def register_org_queue(org_id: int) -> None:
    """Подписать running worker на очередь организации (best-effort)."""
    try:
        slug = _load_slug(org_id)
        if slug:
            register_org_queue_by_slug(slug)
    except Exception:
        logger.exception("register_org_queue failed for org_id=%s", org_id)


def register_org_queue_by_slug(slug: str) -> None:
    try:
        from app.tasks.celery_app import celery

        celery.control.add_consumer(org_queue_name(slug), reply=False)
    except Exception:
        logger.exception("add_consumer failed for slug=%s", slug)


def unregister_org_queue_by_slug(slug: str) -> None:
    try:
        from app.tasks.celery_app import celery

        celery.control.cancel_consumer(org_queue_name(slug), reply=False)
    except Exception:
        logger.exception("cancel_consumer failed for slug=%s", slug)


def _mgmt_auth() -> tuple[str, str]:
    url = settings.rabbitmq_url
    if url.startswith("amqp://"):
        rest = url[7:]
        if "@" in rest:
            creds, _ = rest.split("@", 1)
            if ":" in creds:
                user, password = creds.split(":", 1)
                return user, password
    return "guest", "guest"


def list_rabbitmq_queue_names() -> list[str]:
    user, password = _mgmt_auth()
    try:
        resp = httpx.get(f"{RABBITMQ_MGMT_URL}/queues", auth=(user, password), timeout=5.0)
        resp.raise_for_status()
        return [item["name"] for item in resp.json() if item.get("vhost") == "/"]
    except Exception:
        logger.exception("failed to list RabbitMQ queues")
        return []


def delete_rabbitmq_queue(queue_name: str) -> bool:
    user, password = _mgmt_auth()
    encoded = quote(queue_name, safe="")
    try:
        resp = httpx.delete(
            f"{RABBITMQ_MGMT_URL}/queues/%2F/{encoded}",
            auth=(user, password),
            params={"if-unused": "false", "if-empty": "false"},
            timeout=5.0,
        )
        if resp.status_code in (200, 204, 404):
            logger.info("RabbitMQ queue deleted: %s", queue_name)
            return True
        logger.warning("RabbitMQ queue delete %s: HTTP %s %s", queue_name, resp.status_code, resp.text[:200])
    except Exception:
        logger.exception("failed to delete RabbitMQ queue %s", queue_name)
    return False


def delete_org_queue(org_id: int) -> None:
    slug = _load_slug(org_id)
    if slug:
        delete_org_queue_by_slug(slug)


def delete_org_queue_by_slug(slug: str) -> None:
    queue_name = org_queue_name(slug)
    unregister_org_queue_by_slug(slug)
    if not delete_rabbitmq_queue(queue_name):
        logger.warning("queue %s still present after delete attempt", queue_name)


def sync_org_queues_with_db() -> dict[str, list[str]]:
    """
    Приводит RabbitMQ в соответствие с БД: удаляет лишние org-* / org_* очереди.
    Вызывается при старте backend и worker.
    """
    removed = cleanup_stale_org_queues()
    active = list_worker_queues()
    return {"removed": removed, "active": active}


def cleanup_stale_org_queues() -> list[str]:
    """
    Удаляет очереди org-{slug} без организации в БД и legacy org_{id} / org_None.
    """
    active_slugs = set(list_organization_slugs())
    active_names = {org_queue_name(s) for s in active_slugs}
    removed: list[str] = []

    for queue_name in list_rabbitmq_queue_names():
        if queue_name in (PLATFORM_QUEUE,) or queue_name.startswith("celery"):
            continue
        stale = False
        if LEGACY_ORG_QUEUE_RE.match(queue_name):
            stale = True
        elif queue_name.startswith(ORG_QUEUE_PREFIX) and queue_name not in active_names:
            stale = True
        if stale and delete_rabbitmq_queue(queue_name):
            removed.append(queue_name)

    if removed:
        logger.info("cleaned stale org queues: %s", ", ".join(removed))
    return removed
