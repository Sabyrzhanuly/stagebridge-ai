from datetime import datetime
from pydantic import BaseModel


BACKUP_FORMATS = ("custom", "plain", "tar")


class BackupRequest(BaseModel):
    server_id: int
    database_name: str
    backup_format: str = "custom"
    excluded_tables: list[str] = []
    storage_ids: list[int] | None = None


class BackupScheduleCreate(BaseModel):
    server_id: int
    database_name: str
    cron_expression: str
    retention_days: int = 30
    storage_ids: list[int] | None = None


class BackupScheduleOut(BaseModel):
    id: int
    server_id: int
    database_name: str
    cron_expression: str
    retention_days: int
    storage_ids: list[int] | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BackupHistoryOut(BaseModel):
    id: int
    server_id: int
    database_name: str
    status: str
    stage: str | None = None
    task_id: str | None = None
    backup_format: str | None = None
    file_path: str | None
    storage_id: int | None = None
    storage_name: str | None = None
    file_size: int | None
    checksum: str | None = None
    duration_seconds: int | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class RestoreHistoryOut(BaseModel):
    id: int
    server_id: int
    server_name: str | None = None
    database_name: str
    status: str
    task_id: str | None = None
    backup_id: int | None = None
    backup_format: str | None = None
    file_path: str | None = None
    duration_seconds: int | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class RestoreRequest(BaseModel):
    server_id: int
    database_name: str
    backup_id: int


class BackupDeleteBulkRequest(BaseModel):
    ids: list[int]
