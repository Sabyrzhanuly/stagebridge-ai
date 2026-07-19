"""Публикация статуса Celery worker в WS (вместо клиентского поллинга).

Один серверный цикл делает Celery inspect (ping/active/reserved) и рассылает
результат через Redis pub/sub → WS раздаёт всем подключённым клиентам. Так N
вкладок не плодят N× блокирующих inspect-RPC к воркеру: нагрузка константна.

Права: в платформенный канал уходит полная версия (с деталями задач), в
org-каналы — только счётчики (детали задач не утекают не-админам)."""
from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis

from app.config import settings
from app.services.event_bus import PLATFORM_CHANNEL, org_events_channel

# Кэш последнего статуса — чтобы отдать свежей WS-вкладке сразу, не дожидаясь тика.
CACHE_PLATFORM = "pgadmin:worker_status:platform"
CACHE_ORG = "pgadmin:worker_status:org"
CACHE_TTL = 30            # сек: статус старше — считаем неизвестным
PUBLISH_INTERVAL = 12     # сек между inspect-опросами


def _format_tasks(worker_tasks: dict | None) -> list[dict]:
    result: list[dict] = []
    for worker, tasks in (worker_tasks or {}).items():
        for t in tasks:
            result.append({
                "task_id": t.get("id", ""),
                "name": t.get("name", t.get("type", "")),
                "args": t.get("args", []),
                "kwargs": t.get("kwargs", {}),
                "worker": worker,
                "started": t.get("time_start"),
            })
    return result


def _collect_status_sync() -> dict:
    """Синхронный Celery inspect — вызывать в threadpool (блокирующий RPC)."""
    from app.tasks.celery_app import celery
    inspector = celery.control.inspect(timeout=5)
    try:
        pong = inspector.ping()
    except Exception:  # noqa: BLE001
        pong = None
    online = isinstance(pong, dict) and len(pong) > 0
    active: list[dict] = []
    reserved: list[dict] = []
    if online:
        try:
            active = _format_tasks(inspector.active())
            reserved = _format_tasks(inspector.reserved())
        except Exception:  # noqa: BLE001
            pass
    return {
        "online": online,
        "active": active,
        "reserved": reserved,
        "active_count": len(active),
        "reserved_count": len(reserved),
    }


def _lite(status: dict) -> dict:
    """Без деталей задач: счётчики видят все, список задач — только platform."""
    return {
        "online": status["online"],
        "active": [],
        "reserved": [],
        "active_count": status["active_count"],
        "reserved_count": status["reserved_count"],
    }


async def _org_ids() -> list[int]:
    from sqlalchemy import text
    from app.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            rows = await db.execute(text("SELECT id FROM organizations"))
            return [r[0] for r in rows.all()]
    except Exception:  # noqa: BLE001
        return []


async def worker_status_publisher() -> None:
    """Бесконечный цикл: inspect → publish (platform=детали, org=счётчики) → кэш.
    Отменяется на shutdown приложения (CancelledError пробрасываем)."""
    r = aioredis.from_url(settings.redis_url)
    try:
        while True:
            try:
                status = await asyncio.to_thread(_collect_status_sync)
                full = json.dumps({"type": "worker_status", "data": status}, default=str)
                lite = json.dumps({"type": "worker_status", "data": _lite(status)}, default=str)

                # Кэш для отдачи при коннекте новой вкладки.
                await r.set(CACHE_PLATFORM, full, ex=CACHE_TTL)
                await r.set(CACHE_ORG, lite, ex=CACHE_TTL)

                # Рассылка: платформенный канал — детали, org-каналы — счётчики.
                await r.publish(PLATFORM_CHANNEL, full)
                for oid in await _org_ids():
                    await r.publish(org_events_channel(oid), lite)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(PUBLISH_INTERVAL)
    finally:
        try:
            await r.aclose()
        except Exception:  # noqa: BLE001
            pass
