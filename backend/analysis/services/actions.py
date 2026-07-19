from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .preflight import preview_identifier, preview_table
from .types import ControlledAction

ALLOWED_ACTION_TYPES = {
    "reject_refresh",
    "backfill_null_with_default",
    "normalize_numeric_values",
    "map_enum_values",
    "remove_or_remap_orphans",
    "deduplicate_values",
    "map_renamed_column",
    "postpone_constraint",
    "validate_constraint",
}


def validate_action_payload(payload: dict[str, Any]) -> ControlledAction:
    try:
        action = ControlledAction.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if action.action_type not in ALLOWED_ACTION_TYPES:
        raise ValueError(f"Unsupported action type: {action.action_type}")
    return action


def render_sql_preview(action_type: str, parameters: dict[str, Any]) -> str:
    if action_type not in ALLOWED_ACTION_TYPES:
        raise ValueError(f"Unsupported action type: {action_type}")
    schema = str(parameters.get("schema") or "public")
    table = str(parameters.get("table") or "target_table")
    column = str(parameters.get("column") or "target_column")
    previews = {
        "reject_refresh": "-- no SQL executed; refresh is rejected",
        "backfill_null_with_default": f"UPDATE {preview_table(table, schema)} SET {preview_identifier(column)} = :approved_default WHERE {preview_identifier(column)} IS NULL;",
        "normalize_numeric_values": f"-- Stage and validate casts for {preview_table(table, schema)}.{preview_identifier(column)}; reject invalid rows.",
        "map_enum_values": f"-- Apply only an approved enum mapping to {preview_table(table, schema)}.{preview_identifier(column)}.",
        "remove_or_remap_orphans": f"-- Reject or explicitly remap orphaned keys in {preview_table(table, schema)}.",
        "deduplicate_values": f"-- Load one row per approved unique key in {preview_table(table, schema)}; retain rejected duplicates.",
        "map_renamed_column": f"-- Map {preview_identifier(str(parameters.get('source_column') or 'source_column'))} to {preview_identifier(str(parameters.get('target_column') or 'target_column'))} in {preview_table(table, schema)}.",
        "postpone_constraint": "-- no target constraint change in dry run; records the decision only",
        "validate_constraint": "-- Run controlled validation queries; no live DDL is executed.",
    }
    return previews[action_type]


def required_action_types_for_success() -> set[str]:
    return {
        "backfill_null_with_default",
        "normalize_numeric_values",
        "map_enum_values",
        "remove_or_remap_orphans",
        "deduplicate_values",
        "map_renamed_column",
    }
