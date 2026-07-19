from datetime import datetime
from pydantic import BaseModel


class ChannelCreate(BaseModel):
    name: str
    channel_type: str
    config: dict


class ChannelOut(BaseModel):
    id: int
    name: str
    channel_type: str
    config_json: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str
    threshold: dict
    channel_id: int
    server_id: int | None = None


class ChannelUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class AlertRuleUpdate(BaseModel):
    is_active: bool


class AlertRuleEdit(BaseModel):
    name: str | None = None
    rule_type: str | None = None
    threshold: dict | None = None
    channel_id: int | None = None
    server_id: int | None = None


class AlertRuleOut(BaseModel):
    id: int
    name: str
    rule_type: str
    threshold_json: str
    channel_id: int
    channel_name: str | None = None
    server_id: int | None
    server_name: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationHistoryOut(BaseModel):
    id: int
    channel_id: int
    channel_name: str | None = None
    rule_id: int | None
    rule_name: str | None = None
    server_name: str | None = None
    message: str
    status: str
    sent_at: datetime

    model_config = {"from_attributes": True}


class SmtpSettingsOut(BaseModel):
    configured: bool
    source: str | None = None
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_from: str = ""
    use_tls: bool = True
    has_password: bool = False
    env_fallback: bool = False


class SmtpSettingsUpdate(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_from: str = ""
    use_tls: bool = True
    smtp_password: str | None = None


class SmtpDetectRequest(BaseModel):
    email: str


class SmtpTestRequest(BaseModel):
    to: str | None = None
