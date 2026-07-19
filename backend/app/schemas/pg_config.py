from pydantic import BaseModel


class PgSettingOut(BaseModel):
    name: str
    setting: str | None
    unit: str | None
    category: str | None
    context: str | None
    source: str | None
    sourcefile: str | None
    sourceline: int | None
    pending_restart: bool | None


class PgFileSettingOut(BaseModel):
    sourcefile: str | None
    sourceline: int | None
    seqno: int | None
    name: str
    setting: str | None
    applied: bool
    error: str | None


class PgHbaRuleOut(BaseModel):
    rule_number: int | None
    file_name: str | None
    line_number: int | None
    type: str
    databases: str
    users: str
    address: str | None
    netmask: str | None
    auth_method: str | None
    options: str | None
    error: str | None


class PgConfigPaths(BaseModel):
    config_file: str | None
    hba_file: str | None


class PgConfigSnapshot(BaseModel):
    server_name: str
    pg_major_version: int | None = None
    is_superuser: bool
    paths: PgConfigPaths
    settings: list[PgSettingOut]
    file_settings: list[PgFileSettingOut] | None = None
    file_settings_error: str | None = None
    hba_rules: list[PgHbaRuleOut] | None = None
    hba_error: str | None = None
