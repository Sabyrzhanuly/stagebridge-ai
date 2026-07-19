from datetime import datetime
from pydantic import BaseModel


class ServerCreate(BaseModel):
    name: str
    host: str
    port: int = 5432
    admin_user: str = "postgres"
    admin_password: str
    ssh_user: str | None = None
    environment: str = "dev"
    organization_id: int | None = None


class ServerUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    admin_user: str | None = None
    admin_password: str | None = None
    ssh_user: str | None = None
    environment: str | None = None
    is_active: bool | None = None


class ServerOut(BaseModel):
    id: int
    name: str
    host: str
    port: int
    admin_user: str
    ssh_user: str | None
    environment: str
    is_active: bool
    pg_major_version: int | None = None
    organization_id: int | None = None
    organization_name: str | None = None
    storage_id: int | None = None
    storage_name: str | None = None
    health_status: str = "unknown"
    health_error: str | None = None
    health_error_code: str | None = None
    health_error_title: str | None = None
    health_error_hint: str | None = None
    health_fail_count: int = 0
    health_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ServerOrganizationAssign(BaseModel):
    organization_id: int


class ServerTestResult(BaseModel):
    success: bool
    version: str | None = None
    error: str | None = None
    error_code: str | None = None
    error_title: str | None = None
    error_hint: str | None = None


class ServerHealthOut(BaseModel):
    status: str
    error: str | None = None
    error_code: str | None = None
    error_title: str | None = None
    error_hint: str | None = None
    fail_count: int = 0
    checked_at: datetime | None = None
