from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["Safe", "Warning", "Blocking"]
ConflictCategory = Literal[
    "table_added",
    "table_removed",
    "column_added",
    "column_removed",
    "nullable_to_not_null",
    "nullability_change",
    "incompatible_type_change",
    "text_to_integer",
    "varchar_length_reduction",
    "type_change",
    "default_change",
    "enum_value_mismatch",
    "enum_added",
    "enum_removed",
    "enum_changed",
    "new_foreign_key_orphans",
    "foreign_key_removed",
    "foreign_key_changed",
    "new_unique_constraint_duplicates",
    "unique_constraint_removed",
    "unique_constraint_changed",
    "primary_key_added",
    "primary_key_removed",
    "primary_key_changed",
    "check_constraint_added",
    "check_constraint_removed",
    "check_constraint_changed",
    "index_added",
    "index_removed",
    "index_changed",
    "sequence_added",
    "sequence_removed",
    "sequence_changed",
    "probable_column_rename",
    "routine_added",
    "routine_removed",
    "routine_changed",
    "view_added",
    "view_removed",
    "view_changed",
    "trigger_added",
    "trigger_removed",
    "trigger_changed",
]


class ColumnMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    table_name: str
    name: str
    ordinal_position: int
    data_type: str
    normalized_type: str
    nullable: bool
    default: str | None = None
    max_length: int | None = None
    numeric_precision: int | None = None
    numeric_scale: int | None = None


class ConstraintMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    table_name: str
    name: str
    constraint_type: Literal["primary_key", "foreign_key", "unique", "check", "other"]
    columns: list[str] = Field(default_factory=list)
    definition: str
    referenced_schema: str | None = None
    referenced_table: str | None = None
    referenced_columns: list[str] = Field(default_factory=list)


class IndexMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    table_name: str
    name: str
    definition: str


class EnumMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    name: str
    values: list[str]


class SequenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    name: str
    data_type: str | None = None
    start_value: str | None = None
    increment: str | None = None


class TableMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    name: str
    columns: dict[str, ColumnMetadata] = Field(default_factory=dict)
    constraints: list[ConstraintMetadata] = Field(default_factory=list)
    indexes: list[IndexMetadata] = Field(default_factory=list)


class RoutineMetadata(BaseModel):
    """Хранимая функция или процедура. definition — самодостаточный CREATE OR REPLACE."""

    model_config = ConfigDict(extra="forbid")

    schema_name: str
    name: str
    identity_args: str = ""  # сигнатура аргументов — для различения перегрузок
    kind: str = "function"   # function | procedure
    definition: str = ""


class ViewMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    name: str
    materialized: bool = False
    definition: str = ""


class TriggerMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str
    table_name: str
    name: str
    definition: str = ""


class SchemaSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_name: str
    schemas: list[str]
    tables: dict[str, TableMetadata]
    enums: dict[str, EnumMetadata]
    sequences: list[SequenceMetadata]
    routines: dict[str, RoutineMetadata] = Field(default_factory=dict)
    views: dict[str, ViewMetadata] = Field(default_factory=dict)
    triggers: dict[str, TriggerMetadata] = Field(default_factory=dict)


class PreflightEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    affected_row_count: int = 0
    sample_values: list[Any] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    status: Literal["not_run", "checked", "unsupported_preflight", "error"] = "not_run"
    explanation: str = ""
    sql_preview: str = ""


class ConflictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    schema_name: str
    table_name: str
    column_name: str = ""
    constraint_name: str = ""
    category: ConflictCategory
    object_type: Literal["table", "column", "constraint", "index", "enum", "sequence", "routine", "view", "trigger"]
    change_type: Literal["added", "removed", "changed", "renamed"]
    severity: Severity
    breaking: bool = False
    production_definition: dict[str, Any]
    development_definition: dict[str, Any]
    affected_row_count: int = 0
    sample_values: list[Any] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    preflight_status: Literal["not_run", "checked", "unsupported_preflight", "error"] = "not_run"
    preflight_explanation: str = ""
    sql_preview: str = ""
    strategies: list[str] = Field(default_factory=list)


class ControlledAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: Literal[
        "reject_refresh",
        "backfill_null_with_default",
        "normalize_numeric_values",
        "map_enum_values",
        "remove_or_remap_orphans",
        "deduplicate_values",
        "map_renamed_column",
        "postpone_constraint",
        "validate_constraint",
    ]
    conflict_id: str = ""
    rationale: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_human_approval: bool = True


class RemediationPlanModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_risk_level: Literal["Safe", "Warning", "Blocking"]
    short_explanation: str
    blocking_issues: list[str]
    ordered_recommended_actions: list[ControlledAction]
    alternative_strategies: list[str]
    actions_requiring_human_approval: list[str]
    validation_checks: list[str]
    rollback_considerations: list[str]
