import json
from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator


class ScenarioCreate(BaseModel):
    name: str
    source_server_id: int
    source_database: str
    target_server_id: int
    target_database: str
    old_db_action: str = "drop"
    excluded_tables: list[str] = []
    cron_expression: str | None = None
    is_active: bool = True

    @field_validator("old_db_action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ("drop", "rename"):
            raise ValueError("old_db_action must be 'drop' or 'rename'")
        return v


class ScenarioUpdate(BaseModel):
    name: str | None = None
    source_server_id: int | None = None
    source_database: str | None = None
    target_server_id: int | None = None
    target_database: str | None = None
    old_db_action: str | None = None
    excluded_tables: list[str] | None = None
    cron_expression: str | None = None
    is_active: bool | None = None


class ScenarioOut(BaseModel):
    id: int
    name: str
    source_server_id: int
    source_server_name: str | None = None
    source_database: str
    target_server_id: int
    target_server_name: str | None = None
    target_database: str
    old_db_action: str
    excluded_tables: list[str] = []
    cron_expression: str | None
    is_active: bool
    created_at: datetime
    last_run: "ScenarioRunOut | None" = None
    # Дамп от прошлого (неудачного) прогона доступен для переиспользования.
    reuse_dump_available: bool = False
    reuse_dump_size: int | None = None
    reuse_dump_at: datetime | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def parse_excluded_tables(cls, data: any) -> any:
        if hasattr(data, "__dict__"):
            raw = getattr(data, "excluded_tables_json", None) or "[]"
            try:
                data.__dict__["excluded_tables"] = json.loads(raw)
            except Exception:
                data.__dict__["excluded_tables"] = []
        elif isinstance(data, dict) and "excluded_tables" not in data:
            raw = data.get("excluded_tables_json") or "[]"
            try:
                data["excluded_tables"] = json.loads(raw)
            except Exception:
                data["excluded_tables"] = []
        return data


class ScenarioRunOut(BaseModel):
    id: int
    scenario_id: int
    task_id: str | None
    status: str
    current_step: str | None
    backup_path: str | None
    renamed_to: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


ScenarioOut.model_rebuild()
