from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User
from app.services.tenancy_service import OrgContext, is_global_admin

_SENSITIVE_KEYS = ("password", "secret", "token", "key")
MAX_AI_AUDIT_RECORDS = 200
MAX_AI_PAYLOAD_TEXT = 800


def client_ip(request: Request | None) -> str | None:
  if request is None:
    return None
  forwarded = request.headers.get("X-Forwarded-For")
  if forwarded:
    return forwarded.split(",")[0].strip()[:45]
  if request.client:
    return request.client.host
  return None


def safe_payload(data: dict[str, Any] | None) -> dict[str, Any] | None:
  if not data:
    return None
  out: dict[str, Any] = {}
  for key, value in data.items():
    key_lower = key.lower()
    if any(part in key_lower for part in _SENSITIVE_KEYS):
      out[key] = "***"
    else:
      out[key] = value
  return out


async def log_audit(
  db: AsyncSession,
  user_id: int | None,
  username: str,
  action: str,
  entity_type: str,
  entity_id: str | None = None,
  payload: dict | None = None,
  result: str = "success",
  ip_address: str | None = None,
  organization_id: int | None = None,
  *,
  commit: bool = True,
):
  entry = AuditLog(
    user_id=user_id,
    username=username,
    organization_id=organization_id,
    action=action,
    entity_type=entity_type,
    entity_id=entity_id,
    payload=safe_payload(payload),
    result=result,
    ip_address=ip_address,
  )
  db.add(entry)
  if commit:
    await db.commit()


async def audit_action(
  db: AsyncSession,
  *,
  user: User | None,
  request: Request | None,
  action: str,
  entity_type: str,
  entity_id: str | int | None = None,
  payload: dict | None = None,
  result: str = "success",
  username: str | None = None,
  organization_id: int | None = None,
  commit: bool = True,
):
  entity_id_str = str(entity_id) if entity_id is not None else None
  await log_audit(
    db,
    user_id=user.id if user else None,
    username=username or (user.username if user else "system"),
    action=action,
    entity_type=entity_type,
    entity_id=entity_id_str,
    payload=payload,
    result=result,
    ip_address=client_ip(request),
    organization_id=organization_id,
    commit=commit,
  )


def _compact_payload(payload: dict | None) -> str | None:
  cleaned = safe_payload(payload)
  if cleaned is None:
    return None
  text = json.dumps(cleaned, ensure_ascii=False, default=str)
  if len(text) <= MAX_AI_PAYLOAD_TEXT:
    return text
  return text[: MAX_AI_PAYLOAD_TEXT - 1] + "…"


def _compact_record(entry: AuditLog) -> dict[str, Any]:
  return {
    "id": entry.id,
    "created_at": entry.created_at.isoformat() if entry.created_at else None,
    "organization_id": entry.organization_id,
    "user_id": entry.user_id,
    "username": entry.username,
    "action": entry.action,
    "entity_type": entry.entity_type,
    "entity_id": entry.entity_id,
    "result": entry.result,
    "ip_address": entry.ip_address,
    "payload": _compact_payload(entry.payload),
  }


async def collect_recent_audit_records(
  db: AsyncSession,
  user: User,
  org: OrgContext | None,
  *,
  limit: int = MAX_AI_AUDIT_RECORDS,
) -> list[dict[str, Any]]:
  safe_limit = max(1, min(limit, MAX_AI_AUDIT_RECORDS))
  stmt = select(AuditLog)
  if not is_global_admin(user):
    if org is None:
      return []
    stmt = stmt.where(AuditLog.organization_id == org.organization_id)
  stmt = stmt.order_by(AuditLog.created_at.desc()).limit(safe_limit)
  result = await db.execute(stmt)
  return [_compact_record(entry) for entry in result.scalars().all()]
