import json
from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator


_DATA_MODES = ("new_tables_only", "none")


class StructureSyncCreate(BaseModel):
    name: str
    prod_server_id: int
    prod_database: str
    test_server_id: int
    test_database: str
    # Сервер-приёмник (где собирается новая БД). None → возьмётся prod_server_id.
    target_server_id: int | None = None
    target_name: str
    temp_name_template: str = "{target}_build_{ts}"
    old_db_prefix: str = "to_delete__"
    keep_old_count: int = 0
    data_copy_mode: str = "new_tables_only"
    excluded_tables: list[str] = []
    require_approval: bool = True
    cron_expression: str | None = None
    is_active: bool = True

    @field_validator("data_copy_mode")
    @classmethod
    def validate_data_mode(cls, v: str) -> str:
        if v not in _DATA_MODES:
            raise ValueError(f"data_copy_mode must be one of {_DATA_MODES}")
        return v


class StructureSyncUpdate(BaseModel):
    name: str | None = None
    prod_server_id: int | None = None
    prod_database: str | None = None
    test_server_id: int | None = None
    test_database: str | None = None
    target_server_id: int | None = None
    target_name: str | None = None
    temp_name_template: str | None = None
    old_db_prefix: str | None = None
    keep_old_count: int | None = None
    data_copy_mode: str | None = None
    excluded_tables: list[str] | None = None
    require_approval: bool | None = None
    cron_expression: str | None = None
    is_active: bool | None = None

    @field_validator("data_copy_mode")
    @classmethod
    def validate_data_mode(cls, v: str | None) -> str | None:
        if v is not None and v not in _DATA_MODES:
            raise ValueError(f"data_copy_mode must be one of {_DATA_MODES}")
        return v


class StructureSyncRunOut(BaseModel):
    id: int
    scenario_id: int
    task_id: str | None
    status: str
    current_step: str | None
    temp_db: str | None
    renamed_prod_to: str | None
    dropped_old: list[str] = []
    generated_sql: str | None
    summary: dict | None = None
    dry_run: bool
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def parse_json_fields(cls, data):
        def _load(raw, default):
            try:
                return json.loads(raw) if raw else default
            except Exception:
                return default

        if hasattr(data, "__dict__"):
            data.__dict__["dropped_old"] = _load(getattr(data, "dropped_old_json", None), [])
            data.__dict__["summary"] = _load(getattr(data, "summary_json", None), None)
        elif isinstance(data, dict):
            if "dropped_old" not in data:
                data["dropped_old"] = _load(data.get("dropped_old_json"), [])
            if "summary" not in data:
                data["summary"] = _load(data.get("summary_json"), None)
        return data


class StructureSyncOut(BaseModel):
    id: int
    name: str
    prod_server_id: int
    prod_server_name: str | None = None
    prod_database: str
    test_server_id: int
    test_server_name: str | None = None
    test_database: str
    target_server_id: int | None = None
    target_server_name: str | None = None
    target_name: str
    temp_name_template: str
    old_db_prefix: str
    keep_old_count: int
    data_copy_mode: str
    excluded_tables: list[str] = []
    require_approval: bool
    cron_expression: str | None
    is_active: bool
    created_at: datetime
    last_run: StructureSyncRunOut | None = None

    model_config = {"from_attributes": True}


StructureSyncOut.model_rebuild()
