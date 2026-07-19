import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.notification import NotificationChannel, AlertRule, NotificationHistory
from app.models.server import Server
from app.schemas.notification import (
    ChannelCreate, ChannelUpdate, ChannelOut,
    AlertRuleCreate, AlertRuleUpdate, AlertRuleEdit, AlertRuleOut,
    NotificationHistoryOut,
    SmtpDetectRequest,
)
from app.services.notification_service import send_notification
from app.services import smtp_settings_service
from app.services.audit_service import audit_action
from app.services.tenancy_service import apply_org_filter, get_owned_server, is_global_admin
from app.api.deps import get_auth_context, AuthContext, RequirePermission

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_auth_context)],
)


async def _get_org_channel(channel_id: int, auth: AuthContext, db: AsyncSession) -> NotificationChannel:
    channel = await db.get(NotificationChannel, channel_id)
    if not channel:
        raise HTTPException(404, "Channel not found")
    if not is_global_admin(auth.user) and (
        auth.org is None or channel.organization_id != auth.org.organization_id
    ):
        raise HTTPException(403, "Нет доступа к этому каналу")
    return channel


async def _get_org_rule(rule_id: int, auth: AuthContext, db: AsyncSession) -> AlertRule:
    rule = await db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    if not is_global_admin(auth.user) and (
        auth.org is None or rule.organization_id != auth.org.organization_id
    ):
        raise HTTPException(403, "Нет доступа к этому правилу")
    return rule


async def _validate_rule_refs(
    auth: AuthContext,
    db: AsyncSession,
    channel_id: int,
    server_id: int | None,
) -> None:
    await _get_org_channel(channel_id, auth, db)
    if server_id is not None:
        await get_owned_server(server_id, auth.user, auth.org, db)


def _require_org(auth: AuthContext) -> int:
    if auth.org is None:
        raise HTTPException(403, "Доступно только участникам организации")
    return auth.org.organization_id


def _parse_channel_config(channel: NotificationChannel) -> dict:
    try:
        return json.loads(channel.config_json)
    except json.JSONDecodeError:
        return {}


def _channel_to_out(channel: NotificationChannel) -> ChannelOut:
    cfg_raw = channel.config_json
    if channel.channel_type == "email":
        cfg = _parse_channel_config(channel)
        cfg_raw = json.dumps(smtp_settings_service.sanitize_email_channel_config(cfg))
    return ChannelOut(
        id=channel.id,
        name=channel.name,
        channel_type=channel.channel_type,
        config_json=cfg_raw,
        is_active=channel.is_active,
        created_at=channel.created_at,
    )


def _prepare_channel_config(
    channel_type: str,
    config: dict,
    existing: dict | None = None,
) -> dict:
    if channel_type == "telegram":
        if not config.get("bot_token"):
            raise HTTPException(400, "Укажите Bot Token")
        if not config.get("chat_id"):
            raise HTTPException(400, "Укажите Chat ID")
        return config
    if channel_type == "email":
        try:
            return smtp_settings_service.prepare_email_channel_config(config, existing)
        except ValueError as e:
            raise HTTPException(400, str(e))
    raise HTTPException(400, f"Неизвестный тип канала: {channel_type}")


@router.post("/smtp/detect")
async def detect_smtp_settings(
    data: SmtpDetectRequest,
    _: AuthContext = Depends(get_auth_context),
    __=Depends(RequirePermission("manage_notifications")),
):
    try:
        return smtp_settings_service.detect_from_email(data.email)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/channels", response_model=list[ChannelOut])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    stmt = apply_org_filter(
        select(NotificationChannel), auth.user, auth.org, NotificationChannel.organization_id
    )
    result = await db.execute(stmt.order_by(NotificationChannel.id))
    return [_channel_to_out(ch) for ch in result.scalars().all()]


@router.post("/channels", response_model=ChannelOut, status_code=201)
async def create_channel(
    data: ChannelCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.org is None:
        raise HTTPException(403, "Создание каналов доступно участникам организации")
    prepared = _prepare_channel_config(data.channel_type, data.config)
    channel = NotificationChannel(
        name=data.name,
        channel_type=data.channel_type,
        config_json=json.dumps(prepared),
        organization_id=auth.org.organization_id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="notification_channel",
        entity_id=channel.id,
        payload={"name": channel.name, "channel_type": channel.channel_type},
        organization_id=auth.org.organization_id,
    )
    return _channel_to_out(channel)


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    channel = await _get_org_channel(channel_id, auth, db)
    smtp = None
    if channel.channel_type == "email":
        cfg = _parse_channel_config(channel)
        smtp = smtp_settings_service.smtp_from_channel_config(cfg)
        if not smtp:
            raise HTTPException(400, "SMTP не настроен в канале")
    result = await send_notification(
        channel.channel_type,
        channel.config_json,
        "Test message from PG Control Center",
        smtp=smtp,
    )
    return {"success": result.ok, "message": result.message}


@router.put("/channels/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: int,
    data: ChannelUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    channel = await _get_org_channel(channel_id, auth, db)
    if data.name is not None:
        channel.name = data.name
    if data.config is not None:
        existing = _parse_channel_config(channel) if channel.channel_type == "email" else None
        prepared = _prepare_channel_config(channel.channel_type, data.config, existing)
        channel.config_json = json.dumps(prepared)
    if data.is_active is not None:
        channel.is_active = data.is_active
    await db.commit()
    await db.refresh(channel)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="notification_channel",
        entity_id=channel.id,
        payload=data.model_dump(exclude_unset=True),
        organization_id=auth.org.organization_id if auth.org else None,
    )
    return _channel_to_out(channel)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    channel = await _get_org_channel(channel_id, auth, db)
    channel_name = channel.name
    await db.delete(channel)
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="notification_channel",
        entity_id=channel_id,
        payload={"name": channel_name},
        organization_id=auth.org.organization_id if auth.org else None,
    )


async def _enrich_rules(rules: list[AlertRule], db: AsyncSession) -> list[dict]:
    channel_ids = {r.channel_id for r in rules}
    server_ids = {r.server_id for r in rules if r.server_id}

    channel_map: dict[int, str] = {}
    if channel_ids:
        ch_result = await db.execute(
            select(NotificationChannel).where(NotificationChannel.id.in_(channel_ids))
        )
        channel_map = {c.id: c.name for c in ch_result.scalars().all()}

    server_map: dict[int, str] = {}
    if server_ids:
        sv_result = await db.execute(
            select(Server).where(Server.id.in_(server_ids))
        )
        server_map = {s.id: s.name for s in sv_result.scalars().all()}

    return [
        {
            "id": r.id,
            "name": r.name,
            "rule_type": r.rule_type,
            "threshold_json": r.threshold_json,
            "channel_id": r.channel_id,
            "channel_name": channel_map.get(r.channel_id),
            "server_id": r.server_id,
            "server_name": server_map.get(r.server_id) if r.server_id else None,
            "is_active": r.is_active,
            "created_at": r.created_at,
        }
        for r in rules
    ]


@router.get("/rules", response_model=list[AlertRuleOut])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    stmt = apply_org_filter(select(AlertRule), auth.user, auth.org, AlertRule.organization_id)
    result = await db.execute(stmt.order_by(AlertRule.id))
    rules = result.scalars().all()
    return await _enrich_rules(rules, db)


@router.post("/rules", response_model=AlertRuleOut, status_code=201)
async def create_rule(
    data: AlertRuleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if auth.org is None:
        raise HTTPException(403, "Создание правил доступно участникам организации")
    await _validate_rule_refs(auth, db, data.channel_id, data.server_id)
    rule = AlertRule(
        name=data.name,
        rule_type=data.rule_type,
        threshold_json=json.dumps(data.threshold),
        channel_id=data.channel_id,
        server_id=data.server_id,
        organization_id=auth.org.organization_id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="create",
        entity_type="alert_rule",
        entity_id=rule.id,
        payload={"name": rule.name, "rule_type": rule.rule_type},
        organization_id=auth.org.organization_id,
    )
    enriched = await _enrich_rules([rule], db)
    return enriched[0]


@router.put("/rules/{rule_id}", response_model=AlertRuleOut)
async def update_rule(
    rule_id: int,
    data: AlertRuleEdit,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    rule = await _get_org_rule(rule_id, auth, db)
    ch_id = data.channel_id if data.channel_id is not None else rule.channel_id
    srv_id = data.server_id if data.server_id is not None else rule.server_id
    if data.channel_id is not None or data.server_id is not None:
        await _validate_rule_refs(auth, db, ch_id, srv_id)
    if data.name is not None:
        rule.name = data.name
    if data.rule_type is not None:
        rule.rule_type = data.rule_type
    if data.threshold is not None:
        rule.threshold_json = json.dumps(data.threshold)
    if data.channel_id is not None:
        rule.channel_id = data.channel_id
    if data.server_id is not None:
        rule.server_id = data.server_id
    await db.commit()
    await db.refresh(rule)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="alert_rule",
        entity_id=rule.id,
        payload=data.model_dump(exclude_unset=True),
        organization_id=auth.org.organization_id if auth.org else None,
    )
    enriched = await _enrich_rules([rule], db)
    return enriched[0]


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut)
async def toggle_rule(
    rule_id: int,
    data: AlertRuleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    rule = await _get_org_rule(rule_id, auth, db)
    rule.is_active = data.is_active
    await db.commit()
    await db.refresh(rule)
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="update",
        entity_type="alert_rule",
        entity_id=rule.id,
        payload={"is_active": data.is_active},
        organization_id=auth.org.organization_id if auth.org else None,
    )
    enriched = await _enrich_rules([rule], db)
    return enriched[0]


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    rule = await _get_org_rule(rule_id, auth, db)
    rule_name = rule.name
    await db.delete(rule)
    await db.commit()
    await audit_action(
        db,
        user=auth.user,
        request=request,
        action="delete",
        entity_type="alert_rule",
        entity_id=rule_id,
        payload={"name": rule_name},
        organization_id=auth.org.organization_id if auth.org else None,
    )


@router.get("/history", response_model=list[NotificationHistoryOut])
async def list_notification_history(
    limit: int = Query(100, le=500),
    channel_id: int | None = Query(None),
    server_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    if channel_id is not None:
        await _get_org_channel(channel_id, auth, db)
        stmt = select(NotificationHistory).where(NotificationHistory.channel_id == channel_id)
        if server_id is not None:
            rules_stmt = apply_org_filter(
                select(AlertRule.id).where(
                    AlertRule.channel_id == channel_id,
                    AlertRule.server_id == server_id,
                ),
                auth.user,
                auth.org,
                AlertRule.organization_id,
            )
            rule_ids_result = await db.execute(rules_stmt)
            rule_ids = [r for r, in rule_ids_result.all()]
            if not rule_ids:
                return []
            stmt = stmt.where(NotificationHistory.rule_id.in_(rule_ids))
    else:
        owned_rules_stmt = apply_org_filter(
            select(AlertRule.id), auth.user, auth.org, AlertRule.organization_id
        )
        if server_id is not None:
            owned_rules_stmt = owned_rules_stmt.where(AlertRule.server_id == server_id)
        rule_ids_result = await db.execute(owned_rules_stmt)
        rule_ids = [r for r, in rule_ids_result.all()]
        if not rule_ids:
            return []
        stmt = (
            select(NotificationHistory)
            .where(NotificationHistory.rule_id.in_(rule_ids))
        )

    stmt = stmt.order_by(NotificationHistory.sent_at.desc()).limit(limit)
    result = await db.execute(stmt)
    history = result.scalars().all()

    rule_ids_set = {h.rule_id for h in history if h.rule_id}
    channel_ids_set = {h.channel_id for h in history}

    rule_map: dict[int, AlertRule] = {}
    if rule_ids_set:
        r_result = await db.execute(
            select(AlertRule).where(AlertRule.id.in_(rule_ids_set))
        )
        rule_map = {r.id: r for r in r_result.scalars().all()}

    server_ids_set = {r.server_id for r in rule_map.values() if r.server_id}
    server_map: dict[int, str] = {}
    if server_ids_set:
        sv_result = await db.execute(
            select(Server).where(Server.id.in_(server_ids_set))
        )
        server_map = {s.id: s.name for s in sv_result.scalars().all()}

    channel_map: dict[int, str] = {}
    if channel_ids_set:
        ch_result = await db.execute(
            select(NotificationChannel).where(NotificationChannel.id.in_(channel_ids_set))
        )
        channel_map = {c.id: c.name for c in ch_result.scalars().all()}

    out = []
    for h in history:
        rule = rule_map.get(h.rule_id) if h.rule_id else None
        out.append({
            "id": h.id,
            "channel_id": h.channel_id,
            "channel_name": channel_map.get(h.channel_id),
            "rule_id": h.rule_id,
            "rule_name": rule.name if rule else None,
            "server_name": server_map.get(rule.server_id) if rule and rule.server_id else None,
            "message": h.message,
            "status": h.status,
            "sent_at": h.sent_at,
        })
    return out
