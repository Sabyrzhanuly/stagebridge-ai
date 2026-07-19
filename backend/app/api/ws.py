import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import redis.asyncio as aioredis

from app.config import settings
from app.services.auth_service import decode_token, is_platform_admin
from app.services.event_bus import PLATFORM_CHANNEL, org_events_channel
from app.services.worker_status_service import CACHE_PLATFORM, CACHE_ORG

router = APIRouter()

_active_connections: set[asyncio.Task] = set()


def _resolve_ws_channels(token: str, org_id_param: str | None) -> tuple[list[str], list[str]]:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise ValueError("invalid token type")

    role = payload.get("role", "")
    org_id = payload.get("org_id")

    if org_id_param:
        try:
            org_id = int(org_id_param)
        except ValueError as exc:
            raise ValueError("invalid org_id") from exc

    channels: list[str] = []
    patterns: list[str] = []
    if is_platform_admin(role):
        channels.append(PLATFORM_CHANNEL)
        if org_id is not None:
            channels.append(org_events_channel(org_id))
        else:
            patterns.append("pgadmin:events:org:*")
    elif org_id is not None:
        channels.append(org_events_channel(org_id))
    else:
        raise ValueError("organization required")

    return channels, patterns


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(...),
    org_id: str | None = Query(None),
):
    try:
        channels, patterns = _resolve_ws_channels(token, org_id)
    except Exception:
        await ws.close(code=4401, reason="Unauthorized")
        return

    await ws.accept()
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    for channel in channels:
        await pubsub.subscribe(channel)
    for pattern in patterns:
        await pubsub.psubscribe(pattern)

    # Сразу отдать последний известный статус worker (не ждать следующий тик
    # публикатора). Платформе — с деталями, org — только счётчики.
    try:
        cache_key = CACHE_PLATFORM if PLATFORM_CHANNEL in channels else CACHE_ORG
        cached = await r.get(cache_key)
        if cached:
            await ws.send_text(cached.decode() if isinstance(cached, bytes) else cached)
    except Exception:
        pass

    task = asyncio.current_task()
    if task:
        _active_connections.add(task)

    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                try:
                    await ws.send_text('{"type":"ping"}')
                except Exception:
                    break
                continue

            if message and message["type"] in ("message", "pmessage"):
                await ws.send_text(message["data"].decode())
            await asyncio.sleep(0.1)
    except (WebSocketDisconnect, asyncio.CancelledError, ConnectionError, OSError):
        pass
    finally:
        if task:
            _active_connections.discard(task)
        try:
            for channel in channels:
                await pubsub.unsubscribe(channel)
            for pattern in patterns:
                await pubsub.punsubscribe(pattern)
            await r.aclose()
        except Exception:
            pass


async def publish_event(org_id: int | None, event_type: str, data: dict) -> None:
    from app.services.event_bus import publish_org_event, publish_platform_event

    if org_id is None:
        publish_platform_event(event_type, data)
    else:
        publish_org_event(org_id, event_type, data)
