"""Redis pub/sub: изолированные каналы событий per-org."""
from __future__ import annotations

import json

import redis as sync_redis

from app.config import settings

PLATFORM_CHANNEL = "pgadmin:events:platform"
LEGACY_CHANNEL = "pgadmin:events"


def org_events_channel(org_id: int) -> str:
    return f"pgadmin:events:org:{org_id}"


def publish_org_event(org_id: int, event_type: str, data: dict) -> None:
    payload = json.dumps({"type": event_type, "data": data}, default=str)
    r = sync_redis.from_url(settings.redis_url)
    try:
        r.publish(org_events_channel(org_id), payload)
    finally:
        r.close()


def publish_platform_event(event_type: str, data: dict) -> None:
    payload = json.dumps({"type": event_type, "data": data}, default=str)
    r = sync_redis.from_url(settings.redis_url)
    try:
        r.publish(PLATFORM_CHANNEL, payload)
    finally:
        r.close()
