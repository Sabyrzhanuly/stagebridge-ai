from __future__ import annotations

from difflib import SequenceMatcher
from typing import Callable, Protocol

from .preflight import preview_identifier, preview_table, unsupported_preflight
from .types import ColumnMetadata, ConflictRecord, ConstraintMetadata, PreflightEvidence, SchemaSnapshot


class PreflightLike(Protocol):
    def nullable_to_not_null(self, schema: str, table: str, column: str) -> PreflightEvidence: ...
    def incompatible_type_to_numeric(self, schema: str, table: str, column: str) -> PreflightEvidence: ...
    def text_to_integer(self, schema: str, table: str, column: str) -> PreflightEvidence: ...
    def varchar_length_reduction(self, schema: str, table: str, column: str, max_length: int) -> PreflightEvidence: ...
    def enum_mismatch(self, schema: str, table: str, column: str, allowed_values: list[str]) -> PreflightEvidence: ...
    def foreign_key_orphans(self, schema: str, table: str, columns: list[str], referenced_schema: str, referenced_table: str, referenced_columns: list[str]) -> PreflightEvidence: ...
    def unique_duplicates(self, schema: str, table: str, columns: list[str]) -> PreflightEvidence: ...
    def probable_rename(self, schema: str, table: str, source_column: str, target_column: str) -> PreflightEvidence: ...


def detect_conflicts(
    prod: SchemaSnapshot,
    dev: SchemaSnapshot,
    preflight: PreflightLike | None = None,
    *,
    preflight_enabled: bool | None = None,
) -> list[ConflictRecord]:
    enabled = bool(preflight) if preflight_enabled is None else preflight_enabled
    conflicts: list[ConflictRecord] = []

    prod_keys = set(prod.tables)
    dev_keys = set(dev.tables)
    for key in sorted(prod_keys - dev_keys):
        table = prod.tables[key]
        conflicts.append(
            _conflict(
                category="table_removed",
                schema=table.schema_name,
                table=table.name,
                object_type="table",
                change_type="removed",
                severity="Warning",
                breaking=True,
                prod_def=table.model_dump(),
                dev_def={"table": "not present"},
                evidence=_not_supported(enabled, "Table removal has no bounded row-level preflight."),
                strategies=["Archive source-only data", "Keep the table in development", "Exclude the table explicitly"],
                sql_preview=f"-- Review only: development removes {preview_table(table.name, table.schema_name)}",
            )
        )
    for key in sorted(dev_keys - prod_keys):
        table = dev.tables[key]
        conflicts.append(
            _conflict(
                category="table_added",
                schema=table.schema_name,
                table=table.name,
                object_type="table",
                change_type="added",
                severity="Safe",
                breaking=False,
                prod_def={"table": "not present"},
                dev_def=table.model_dump(),
                evidence=_not_supported(enabled, "A new target table does not require a production row preflight."),
                strategies=["Verify the table is populated by the application", "Provide defaults for required columns"],
                sql_preview=f"-- Review only: create {preview_table(table.name, table.schema_name)} from the development definition",
            )
        )

    for key in sorted(prod_keys & dev_keys):
        prod_table = prod.tables[key]
        dev_table = dev.tables[key]
        conflicts.extend(_column_diffs(prod, dev, prod_table, dev_table, preflight, enabled))
        conflicts.extend(_constraint_diffs(prod_table, dev_table, preflight, enabled))
        conflicts.extend(_index_diffs(prod_table, dev_table, enabled))

    conflicts.extend(_enum_diffs(prod, dev, enabled))
    conflicts.extend(_sequence_diffs(prod, dev, enabled))
    conflicts.extend(_routine_diffs(prod, dev, enabled))
    conflicts.extend(_view_diffs(prod, dev, enabled))
    conflicts.extend(_trigger_diffs(prod, dev, enabled))
    return _deduplicate(conflicts)


def _norm_def(text: str) -> str:
    """Нормализовать определение объекта для устойчивого сравнения."""
    return " ".join((text or "").split())


def _routine_diffs(prod: SchemaSnapshot, dev: SchemaSnapshot, enabled: bool) -> list[ConflictRecord]:
    result: list[ConflictRecord] = []
    for key in sorted(set(prod.routines) | set(dev.routines)):
        left = prod.routines.get(key)
        right = dev.routines.get(key)
        if left and right and _norm_def(left.definition) == _norm_def(right.definition):
            continue
        item = right or left
        change = "changed" if left and right else "removed" if left else "added"
        result.append(
            _conflict(
                category=f"routine_{change}", schema=item.schema_name, table=f"{item.name}({item.identity_args})",
                object_type="routine", change_type=change,
                severity="Warning", breaking=change == "removed",
                prod_def=left.model_dump() if left else {"routine": "not present"},
                dev_def=right.model_dump() if right else {"routine": "not present"},
                evidence=_not_supported(enabled, f"A {change} {item.kind} is a structural change without a row-level preflight."),
                strategies=["Review the routine body", "Recreate the routine on the target", "Confirm dependent objects"],
                sql_preview=f"-- Review only: {change} {item.kind} {preview_table(item.name, item.schema_name)}",
            )
        )
    return result


def _view_diffs(prod: SchemaSnapshot, dev: SchemaSnapshot, enabled: bool) -> list[ConflictRecord]:
    result: list[ConflictRecord] = []
    for key in sorted(set(prod.views) | set(dev.views)):
        left = prod.views.get(key)
        right = dev.views.get(key)
        if left and right and _norm_def(left.definition) == _norm_def(right.definition) and left.materialized == right.materialized:
            continue
        item = right or left
        change = "changed" if left and right else "removed" if left else "added"
        label = "materialized view" if item.materialized else "view"
        result.append(
            _conflict(
                category=f"view_{change}", schema=item.schema_name, table=item.name,
                object_type="view", change_type=change,
                severity="Warning", breaking=change == "removed",
                prod_def=left.model_dump() if left else {"view": "not present"},
                dev_def=right.model_dump() if right else {"view": "not present"},
                evidence=_not_supported(enabled, f"A {change} {label} is a structural change without a row-level preflight."),
                strategies=["Review the view definition", "Recreate the view on the target", "Confirm dependent queries"],
                sql_preview=f"-- Review only: {change} {label} {preview_table(item.name, item.schema_name)}",
            )
        )
    return result


def _trigger_diffs(prod: SchemaSnapshot, dev: SchemaSnapshot, enabled: bool) -> list[ConflictRecord]:
    result: list[ConflictRecord] = []
    for key in sorted(set(prod.triggers) | set(dev.triggers)):
        left = prod.triggers.get(key)
        right = dev.triggers.get(key)
        if left and right and _norm_def(left.definition) == _norm_def(right.definition):
            continue
        item = right or left
        change = "changed" if left and right else "removed" if left else "added"
        result.append(
            _conflict(
                category=f"trigger_{change}", schema=item.schema_name, table=item.table_name, constraint=item.name,
                object_type="trigger", change_type=change,
                severity="Warning", breaking=False,
                prod_def=left.model_dump() if left else {"trigger": "not present"},
                dev_def=right.model_dump() if right else {"trigger": "not present"},
                evidence=_not_supported(enabled, f"A {change} trigger is a structural change without a row-level preflight."),
                strategies=["Review the trigger definition", "Recreate the trigger on the target", "Confirm the trigger function exists"],
                sql_preview=f"-- Review only: {change} trigger {preview_identifier(item.name)} on {preview_table(item.table_name, item.schema_name)}",
            )
        )
    return result


def _column_diffs(prod, dev, prod_table, dev_table, preflight, enabled: bool) -> list[ConflictRecord]:
    conflicts: list[ConflictRecord] = []
    schema = prod_table.schema_name
    prod_names = set(prod_table.columns)
    dev_names = set(dev_table.columns)

    for name in sorted(prod_names - dev_names):
        column = prod_table.columns[name]
        conflicts.append(
            _conflict(
                category="column_removed", schema=schema, table=prod_table.name, column=name,
                object_type="column", change_type="removed", severity="Warning", breaking=True,
                prod_def=column.model_dump(), dev_def={"column": "not present"},
                evidence=_not_supported(enabled, "Column removal has no safe generic data preflight."),
                strategies=["Map the source column", "Archive ignored data", "Keep a compatibility column"],
                sql_preview=f"-- Review only\nALTER TABLE {preview_table(prod_table.name, schema)} DROP COLUMN {preview_identifier(name)};",
            )
        )
    for name in sorted(dev_names - prod_names):
        column = dev_table.columns[name]
        breaking = not column.nullable and column.default is None
        conflicts.append(
            _conflict(
                category="column_added", schema=schema, table=prod_table.name, column=name,
                object_type="column", change_type="added", severity="Blocking" if breaking else "Safe", breaking=breaking,
                prod_def={"column": "not present"}, dev_def=column.model_dump(),
                evidence=_not_supported(enabled, "New-column population depends on application-specific source mapping."),
                strategies=["Provide a default", "Add the column as nullable first", "Define an explicit source mapping"],
                sql_preview=f"-- Review only: add {preview_identifier(name)} using the development column definition",
            )
        )

    conflicts.extend(_probable_renames(prod_table, dev_table, preflight, enabled))

    for name in sorted(prod_names & dev_names):
        left = prod_table.columns[name]
        right = dev_table.columns[name]
        base_args = {"schema": schema, "table": prod_table.name, "column": name, "object_type": "column", "change_type": "changed"}
        if left.nullable != right.nullable:
            if left.nullable and not right.nullable:
                evidence = _run(enabled, preflight, lambda: preflight.nullable_to_not_null(schema, prod_table.name, name))
                conflicts.append(
                    _conflict(
                        category="nullable_to_not_null", severity=_risk_severity(evidence), breaking=True,
                        prod_def=left.model_dump(), dev_def=right.model_dump(), evidence=evidence,
                        strategies=["Backfill null values", "Add the constraint later", "Reject incompatible rows"],
                        sql_preview=f"ALTER TABLE {preview_table(prod_table.name, schema)} ALTER COLUMN {preview_identifier(name)} SET NOT NULL;",
                        **base_args,
                    )
                )
            else:
                conflicts.append(
                    _conflict(
                        category="nullability_change", severity="Safe", breaking=False,
                        prod_def=left.model_dump(), dev_def=right.model_dump(),
                        evidence=_not_supported(enabled, "Relaxing nullability does not require a production data preflight."),
                        strategies=["Confirm application handling for NULL values"],
                        sql_preview=f"ALTER TABLE {preview_table(prod_table.name, schema)} ALTER COLUMN {preview_identifier(name)} DROP NOT NULL;",
                        **base_args,
                    )
                )

        if left.normalized_type != right.normalized_type:
            category = _type_category(left, right)
            if category == "incompatible_type_change":
                evidence = _run(enabled, preflight, lambda: preflight.incompatible_type_to_numeric(schema, prod_table.name, name))
            elif category == "text_to_integer":
                evidence = _run(enabled, preflight, lambda: preflight.text_to_integer(schema, prod_table.name, name))
            else:
                evidence = _not_supported(enabled, f"No bounded safe preflight is implemented for {left.normalized_type} to {right.normalized_type}.")
            conflicts.append(
                _conflict(
                    category=category, severity=_risk_severity(evidence), breaking=True,
                    prod_def=left.model_dump(), dev_def=right.model_dump(), evidence=evidence,
                    strategies=["Use an explicit USING expression", "Normalize source values", "Stage the type change"],
                    sql_preview=f"ALTER TABLE {preview_table(prod_table.name, schema)} ALTER COLUMN {preview_identifier(name)} TYPE {right.data_type};",
                    **base_args,
                )
            )
        elif left.normalized_type == "varchar" and right.max_length and (left.max_length is None or right.max_length < left.max_length):
            evidence = _run(
                enabled,
                preflight,
                lambda: preflight.varchar_length_reduction(schema, prod_table.name, name, right.max_length),
            )
            conflicts.append(
                _conflict(
                    category="varchar_length_reduction", severity=_risk_severity(evidence), breaking=True,
                    prod_def=left.model_dump(), dev_def=right.model_dump(), evidence=evidence,
                    strategies=["Increase the development limit", "Trim with explicit approval", "Reject oversized values"],
                    sql_preview=f"ALTER TABLE {preview_table(prod_table.name, schema)} ALTER COLUMN {preview_identifier(name)} TYPE varchar({right.max_length});",
                    **base_args,
                )
            )

        if (left.default or "") != (right.default or ""):
            conflicts.append(
                _conflict(
                    category="default_change", severity="Warning", breaking=False,
                    prod_def=left.model_dump(), dev_def=right.model_dump(),
                    evidence=_not_supported(enabled, "Default changes affect future writes, not existing production rows."),
                    strategies=["Confirm application insert behavior", "Review generated expressions and sequences"],
                    sql_preview=f"-- Review only: change default for {preview_table(prod_table.name, schema)}.{preview_identifier(name)}",
                    **base_args,
                )
            )

        enum_conflict = _enum_conflict(prod, dev, left, right)
        if enum_conflict and enum_conflict["removed_values"]:
            evidence = _run(
                enabled,
                preflight,
                lambda: preflight.enum_mismatch(schema, prod_table.name, name, enum_conflict["development_values"]),
            )
            conflicts.append(
                _conflict(
                    category="enum_value_mismatch", severity=_risk_severity(evidence), breaking=True,
                    prod_def={"enum_values": enum_conflict["production_values"], **left.model_dump()},
                    dev_def={"enum_values": enum_conflict["development_values"], **right.model_dump()},
                    evidence=evidence,
                    strategies=["Map removed enum values", "Restore development enum values", "Reject unsupported rows"],
                    sql_preview=f"-- Review only: map removed enum values before changing {preview_table(prod_table.name, schema)}.{preview_identifier(name)}",
                    **base_args,
                )
            )
    return conflicts


def _constraint_diffs(prod_table, dev_table, preflight, enabled: bool) -> list[ConflictRecord]:
    conflicts: list[ConflictRecord] = []
    for constraint_type in ("primary_key", "foreign_key", "unique", "check"):
        prod_items = {item.name: item for item in prod_table.constraints if item.constraint_type == constraint_type}
        dev_items = {item.name: item for item in dev_table.constraints if item.constraint_type == constraint_type}
        for name in sorted(prod_items.keys() & dev_items.keys()):
            if _constraint_signature(prod_items[name]) != _constraint_signature(dev_items[name]):
                conflicts.append(_constraint_change(prod_table, prod_items[name], dev_items[name], "changed", preflight, enabled))
        for name in sorted(prod_items.keys() - dev_items.keys()):
            conflicts.append(_constraint_change(prod_table, prod_items[name], None, "removed", preflight, enabled))
        for name in sorted(dev_items.keys() - prod_items.keys()):
            conflicts.append(_constraint_change(prod_table, None, dev_items[name], "added", preflight, enabled))
    return conflicts


def _constraint_change(prod_table, prod_constraint, dev_constraint, change: str, preflight, enabled: bool) -> ConflictRecord:
    item: ConstraintMetadata = dev_constraint or prod_constraint
    kind = item.constraint_type
    category_map = {
        ("primary_key", "added"): "primary_key_added", ("primary_key", "removed"): "primary_key_removed", ("primary_key", "changed"): "primary_key_changed",
        ("foreign_key", "added"): "new_foreign_key_orphans", ("foreign_key", "removed"): "foreign_key_removed", ("foreign_key", "changed"): "foreign_key_changed",
        ("unique", "added"): "new_unique_constraint_duplicates", ("unique", "removed"): "unique_constraint_removed", ("unique", "changed"): "unique_constraint_changed",
        ("check", "added"): "check_constraint_added", ("check", "removed"): "check_constraint_removed", ("check", "changed"): "check_constraint_changed",
    }
    category = category_map[(kind, change)]
    if kind == "foreign_key" and change == "added" and item.referenced_table:
        evidence = _run(
            enabled,
            preflight,
            lambda: preflight.foreign_key_orphans(
                prod_table.schema_name,
                prod_table.name,
                item.columns,
                item.referenced_schema or prod_table.schema_name,
                item.referenced_table,
                item.referenced_columns,
            ),
        )
    elif kind == "unique" and change == "added":
        evidence = _run(enabled, preflight, lambda: preflight.unique_duplicates(prod_table.schema_name, prod_table.name, item.columns))
    else:
        evidence = _not_supported(enabled, f"No generic row-level preflight is available for a {change} {kind.replace('_', ' ')}.")
    breaking = change in {"added", "changed"} and kind in {"primary_key", "foreign_key", "unique", "check"}
    preview = f"-- Review only: {change} {kind.replace('_', ' ')} {preview_identifier(item.name)} on {preview_table(prod_table.name, prod_table.schema_name)}"
    if change == "added":
        preview = f"ALTER TABLE {preview_table(prod_table.name, prod_table.schema_name)} ADD CONSTRAINT {preview_identifier(item.name)} {item.definition};"
    return _conflict(
        category=category,
        schema=prod_table.schema_name,
        table=prod_table.name,
        constraint=item.name,
        object_type="constraint",
        change_type=change,
        severity=_risk_severity(evidence) if breaking else "Warning",
        breaking=breaking,
        prod_def=prod_constraint.model_dump() if prod_constraint else {"constraint": "not present"},
        dev_def=dev_constraint.model_dump() if dev_constraint else {"constraint": "not present"},
        evidence=evidence,
        strategies=["Validate affected rows", "Add the constraint as NOT VALID where supported", "Stage the constraint change"],
        sql_preview=preview,
    )


def _index_diffs(prod_table, dev_table, enabled: bool) -> list[ConflictRecord]:
    result: list[ConflictRecord] = []
    prod_indexes = {index.name: index for index in prod_table.indexes}
    dev_indexes = {index.name: index for index in dev_table.indexes}
    for name in sorted(prod_indexes.keys() | dev_indexes.keys()):
        left = prod_indexes.get(name)
        right = dev_indexes.get(name)
        if left and right and left.definition == right.definition:
            continue
        change = "changed" if left and right else "removed" if left else "added"
        result.append(
            _conflict(
                category=f"index_{change}", schema=prod_table.schema_name, table=prod_table.name,
                constraint=name, object_type="index", change_type=change,
                severity="Warning" if change != "added" else "Safe", breaking=False,
                prod_def=left.model_dump() if left else {"index": "not present"},
                dev_def=right.model_dump() if right else {"index": "not present"},
                evidence=_not_supported(enabled, "Index changes are structural and have no row-level preflight."),
                strategies=["Review query plans", "Build large indexes concurrently outside this analyzer"],
                sql_preview=f"-- Review only: {change} index {preview_identifier(name)}",
            )
        )
    return result


def _enum_diffs(prod: SchemaSnapshot, dev: SchemaSnapshot, enabled: bool) -> list[ConflictRecord]:
    result: list[ConflictRecord] = []
    keys = set(prod.enums) | set(dev.enums)
    for key in sorted(keys):
        left = prod.enums.get(key)
        right = dev.enums.get(key)
        if left and right and left.values == right.values:
            continue
        item = right or left
        change = "changed" if left and right else "removed" if left else "added"
        category = "enum_changed" if change == "changed" else f"enum_{change}"
        result.append(
            _conflict(
                category=category, schema=item.schema_name, table=item.name,
                object_type="enum", change_type=change,
                severity="Warning", breaking=bool(left and (not right or set(left.values) - set(right.values))),
                prod_def=left.model_dump() if left else {"enum": "not present"},
                dev_def=right.model_dump() if right else {"enum": "not present"},
                evidence=_not_supported(enabled, "Enum usage is preflighted on each affected table column when it can be mapped safely."),
                strategies=["Map removed values", "Add values in a staged migration", "Review enum ordering"],
                sql_preview=f"-- Review only: {change} enum {preview_table(item.name, item.schema_name)}",
            )
        )
    return result


def _sequence_diffs(prod: SchemaSnapshot, dev: SchemaSnapshot, enabled: bool) -> list[ConflictRecord]:
    result: list[ConflictRecord] = []
    prod_items = {f"{item.schema_name}.{item.name}": item for item in prod.sequences}
    dev_items = {f"{item.schema_name}.{item.name}": item for item in dev.sequences}
    for key in sorted(set(prod_items) | set(dev_items)):
        left = prod_items.get(key)
        right = dev_items.get(key)
        if left and right and left.model_dump() == right.model_dump():
            continue
        item = right or left
        change = "changed" if left and right else "removed" if left else "added"
        result.append(
            _conflict(
                category=f"sequence_{change}", schema=item.schema_name, table=item.name,
                object_type="sequence", change_type=change,
                severity="Warning", breaking=False,
                prod_def=left.model_dump() if left else {"sequence": "not present"},
                dev_def=right.model_dump() if right else {"sequence": "not present"},
                evidence=_not_supported(enabled, "Sequence changes require ownership and current-value review outside row preflight."),
                strategies=["Compare current sequence values", "Verify column ownership", "Set values after a controlled load"],
                sql_preview=f"-- Review only: {change} sequence {preview_table(item.name, item.schema_name)}",
            )
        )
    return result


def _probable_renames(prod_table, dev_table, preflight, enabled: bool) -> list[ConflictRecord]:
    prod_only = [column for name, column in prod_table.columns.items() if name not in dev_table.columns]
    dev_only = [column for name, column in dev_table.columns.items() if name not in prod_table.columns]
    conflicts: list[ConflictRecord] = []
    used_targets: set[str] = set()
    for left in prod_only:
        candidates = [right for right in dev_only if right.name not in used_targets and _rename_type_compatible(left, right)]
        if not candidates:
            continue
        right = max(candidates, key=lambda item: _rename_score(left.name, item.name))
        score = _rename_score(left.name, right.name)
        if score < 0.45:
            continue
        used_targets.add(right.name)
        evidence = _run(
            enabled,
            preflight,
            lambda: preflight.probable_rename(prod_table.schema_name, prod_table.name, left.name, right.name),
        )
        evidence.evidence["similarity_score"] = round(score, 3)
        conflicts.append(
            _conflict(
                category="probable_column_rename", schema=prod_table.schema_name, table=prod_table.name,
                column=f"{left.name}->{right.name}", object_type="column", change_type="renamed",
                severity="Warning", breaking=True,
                prod_def=left.model_dump(), dev_def=right.model_dump(), evidence=evidence,
                strategies=["Confirm the rename", "Map source data explicitly", "Treat as separate removed and added columns"],
                sql_preview=f"ALTER TABLE {preview_table(prod_table.name, prod_table.schema_name)} RENAME COLUMN {preview_identifier(left.name)} TO {preview_identifier(right.name)};",
            )
        )
    return conflicts


def _type_category(left: ColumnMetadata, right: ColumnMetadata) -> str:
    if left.normalized_type in {"varchar", "text"} and right.normalized_type == "numeric":
        return "incompatible_type_change"
    if left.normalized_type in {"varchar", "text"} and right.normalized_type in {"smallint", "integer", "bigint"}:
        return "text_to_integer"
    return "type_change"


def _enum_conflict(prod, dev, left, right):
    prod_enum = _find_enum(prod, left.normalized_type)
    dev_enum = _find_enum(dev, right.normalized_type)
    if not prod_enum or not dev_enum or prod_enum.values == dev_enum.values:
        return None
    return {
        "production_values": prod_enum.values,
        "development_values": dev_enum.values,
        "removed_values": sorted(set(prod_enum.values) - set(dev_enum.values)),
    }


def _find_enum(snapshot, type_name):
    return next((item for item in snapshot.enums.values() if item.name == type_name or f"{item.schema_name}.{item.name}" == type_name), None)


def _constraint_signature(item: ConstraintMetadata) -> tuple:
    return (
        item.constraint_type,
        tuple(item.columns),
        item.definition,
        item.referenced_schema,
        item.referenced_table,
        tuple(item.referenced_columns),
    )


def _rename_type_compatible(left: ColumnMetadata, right: ColumnMetadata) -> bool:
    return left.normalized_type == right.normalized_type or {left.normalized_type, right.normalized_type} <= {"varchar", "text"}


def _rename_score(left: str, right: str) -> float:
    synonym_pairs = {("full_name", "display_name"), ("name", "display_name"), ("customer_name", "display_name")}
    if (left, right) in synonym_pairs or (right, left) in synonym_pairs:
        return 0.95
    return SequenceMatcher(None, left.replace("_", ""), right.replace("_", "")).ratio()


def _run(enabled: bool, preflight, operation: Callable[[], PreflightEvidence]) -> PreflightEvidence:
    if not enabled:
        return PreflightEvidence(status="not_run", explanation="Preflight checks were disabled for this analysis.")
    if preflight is None:
        return unsupported_preflight("No production preflight runner was available.")
    try:
        return operation()
    except Exception as exc:
        return PreflightEvidence(status="error", explanation=f"Preflight failed safely: {exc}")


def _not_supported(enabled: bool, reason: str) -> PreflightEvidence:
    if not enabled:
        return PreflightEvidence(status="not_run", explanation="Preflight checks were disabled for this analysis.")
    return unsupported_preflight(reason)


def _risk_severity(evidence: PreflightEvidence) -> str:
    if evidence.status == "error":
        return "Warning"
    return "Blocking" if evidence.affected_row_count else "Warning"


def _conflict(
    *,
    category: str,
    schema: str,
    table: str,
    object_type: str,
    change_type: str,
    severity: str,
    breaking: bool,
    prod_def: dict,
    dev_def: dict,
    evidence: PreflightEvidence,
    strategies: list[str],
    sql_preview: str,
    column: str = "",
    constraint: str = "",
) -> ConflictRecord:
    subject = column or constraint or table
    return ConflictRecord(
        conflict_id=f"{category}:{schema}.{table}:{subject}",
        schema_name=schema,
        table_name=table,
        column_name=column,
        constraint_name=constraint,
        category=category,
        object_type=object_type,
        change_type=change_type,
        severity=severity,
        breaking=breaking,
        production_definition=prod_def,
        development_definition=dev_def,
        affected_row_count=evidence.affected_row_count,
        sample_values=evidence.sample_values,
        evidence=evidence.evidence,
        preflight_status=evidence.status,
        preflight_explanation=evidence.explanation,
        sql_preview=sql_preview,
        strategies=strategies,
    )


def _deduplicate(conflicts: list[ConflictRecord]) -> list[ConflictRecord]:
    return list({item.conflict_id: item for item in conflicts}.values())
