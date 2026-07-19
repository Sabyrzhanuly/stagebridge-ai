"""Обобщённый накат production → изолированная БД для произвольной схемы.

В отличие от demo-исполнителя (:mod:`analysis.services.dry_run`), который жёстко
знает demo-таблицы, этот исполнитель работает с любым снапшотом: строит целевую
схему из development-снапшота, переносит production-строки, применяя
детерминированные исправления по категориям конфликтов, отклонённые строки
складывает в аудит, а корректность проверяет добавлением ограничений после
загрузки. Пишет ТОЛЬКО в изолированную управляемую БД; источники — read-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from analysis.models import AnalysisRun, DryRunLog

from .connections import connect_to_profile, connect_to_profile_writable, connect_to_target
from .localization import translate
from .schema_inspector import SchemaInspector
from .types import ColumnMetadata, SchemaSnapshot, TableMetadata
from . import ddl_builder

NUMERIC_RE = re.compile(r"^\s*[+-]?((\d+(\.\d+)?)|(\.\d+))\s*$")
INTEGER_RE = re.compile(r"^\s*[+-]?\d+\s*$")

_INT_TYPES = {"integer", "bigint", "smallint"}


@dataclass
class MigrationResult:
    passed: bool
    transferred_rows: int = 0
    rejected_rows: int = 0
    validation_failures: int = 0
    row_mismatches: int = 0
    verify: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _ColumnPlan:
    """Как заполнить одну development-колонку из production-строки."""

    column: ColumnMetadata
    source: str | None          # имя исходной production-колонки (None → добавленная)
    kind: str                   # direct | rename | added
    categories: set[str] = field(default_factory=set)
    varchar_limit: int | None = None
    removed_enum: set[str] = field(default_factory=set)
    enum_mapping: dict[str, str] = field(default_factory=dict)
    allowed_enum: set[str] = field(default_factory=set)
    default_value: Any = None


class MigrationExecutor:
    def __init__(self, analysis: AnalysisRun, *, target_key: str = "dryrun", target_profile=None):
        self.analysis = analysis
        self.locale = analysis.locale
        self.target_key = target_key
        self.target_profile = target_profile  # ConnectionProfile role=staging → реальная миграция
        self.sequence = 0
        self.logs: list[dict[str, Any]] = []
        self.verify: list[dict[str, Any]] = []
        self.action_params = {
            action.action_type: action.parameters for action in analysis.actions.all()
        }

    # -- Публичный вход -----------------------------------------------------

    def run(self) -> MigrationResult:
        if self.analysis.status != AnalysisRun.Status.COMPLETED:
            self._log("safety_gate", "failed", translate("migration.not_completed", self.locale))
            return self._finish(MigrationResult(passed=False, validation_failures=1))
        if not self.analysis.actions.exists():
            self._log("plan_gate", "failed", translate("migration.plan_required", self.locale))
            return self._finish(MigrationResult(passed=False, validation_failures=1))

        self.analysis.dry_run_status = AnalysisRun.DryRunStatus.RUNNING
        self.analysis.save(update_fields=["dry_run_status", "updated_at"])
        DryRunLog.objects.filter(analysis=self.analysis).delete()

        schemas = list(self.analysis.selected_schemas or ["public"])
        try:
            with self._source_conn("production") as prod_conn, self._source_conn("development") as dev_conn:
                prod = SchemaInspector(prod_conn, "production", selected_schemas=schemas).inspect()
                dev = SchemaInspector(dev_conn, "development", selected_schemas=schemas).inspect()
                prod_rows = self._read_source_rows(prod_conn, prod, dev)

            target_ctx = (
                connect_to_profile_writable(self.target_profile)
                if self.target_profile is not None
                else connect_to_target(self.target_key, read_only=False, autocommit=False)
            )
            with target_ctx as target_conn:
                try:
                    result = self._apply(target_conn, prod, dev, prod_rows, schemas)
                    if result.passed:
                        target_conn.commit()
                        self._log("commit", "passed", translate("migration.committed", self.locale))
                    else:
                        target_conn.rollback()
                        self._log("rollback", "failed", translate("migration.rolled_back", self.locale))
                except Exception:
                    target_conn.rollback()
                    raise
                return self._finish(result)
        except Exception as exc:  # безопасный сбой: цель откатывается, источники нетронуты
            self._log("migration_error", "failed", f"{translate('migration.failed', self.locale)}: {exc}")
            return self._finish(MigrationResult(passed=False, validation_failures=1))

    # -- Соединения ---------------------------------------------------------

    def _source_conn(self, role: str):
        if self.analysis.mode == AnalysisRun.Mode.LIVE:
            profile = self.analysis.production_profile if role == "production" else self.analysis.development_profile
            return connect_to_profile(profile)
        return connect_to_target("prod" if role == "production" else "dev", read_only=True)

    # -- Чтение источника ---------------------------------------------------

    def _read_source_rows(self, conn, prod: SchemaSnapshot, dev: SchemaSnapshot) -> dict[str, list[dict]]:
        """Считать production-строки для каждой таблицы, присутствующей и в dev."""
        from psycopg import sql

        rows: dict[str, list[dict]] = {}
        for key in sorted(set(prod.tables) & set(dev.tables)):
            table = prod.tables[key]
            column_names = sorted(table.columns, key=lambda name: table.columns[name].ordinal_position)
            select = sql.SQL("SELECT {cols} FROM {schema}.{table}").format(
                cols=sql.SQL(", ").join(sql.Identifier(name) for name in column_names),
                schema=sql.Identifier(table.schema_name),
                table=sql.Identifier(table.name),
            )
            rows[key] = [dict(record) for record in conn.execute(select).fetchall()]
        return rows

    # -- Применение к цели --------------------------------------------------

    def _apply(
        self,
        conn,
        prod: SchemaSnapshot,
        dev: SchemaSnapshot,
        prod_rows: dict[str, list[dict]],
        schemas: list[str],
    ) -> MigrationResult:
        from psycopg import sql

        schema_set = set(schemas)
        self._reset_schemas(conn, schemas)

        for statement in ddl_builder.create_schema_statements(dev, schemas):
            conn.execute(statement)
        for statement in ddl_builder.create_enum_statements(dev, schema_set):
            conn.execute(statement)
        for statement in ddl_builder.create_sequence_statements(dev, schema_set):
            conn.execute(statement)

        ordered = self._topo_sort(dev)
        enums = ddl_builder._enum_lookup(dev)
        for key in ordered:
            conn.execute(ddl_builder.create_table_statement(dev.tables[key], enums))
        self._log("apply_schema", "passed", translate("migration.schema_applied", self.locale))

        transferred = 0
        rejected = 0
        parent_keys: dict[str, set] = {}
        dev_enum_values = {name: set(enum.values) for name, enum in enums.items()}

        for key in ordered:
            if key not in prod.tables:
                continue  # таблица есть только в dev — создаём пустой, без загрузки
            moved, dropped = self._migrate_table(
                conn, prod.tables[key], dev.tables[key], prod_rows.get(key, []), parent_keys, dev_enum_values
            )
            transferred += moved
            rejected += dropped

        failures = self._apply_constraints_and_indexes(conn, dev, ordered)
        failures += self._apply_schema_objects(conn, dev, schema_set)
        mismatches = self._verify_rows(conn)

        return MigrationResult(
            passed=failures == 0 and mismatches == 0,
            transferred_rows=transferred,
            rejected_rows=rejected,
            validation_failures=failures,
            row_mismatches=mismatches,
            verify=self.verify,
            logs=self.logs,
        )

    def _verify_rows(self, conn) -> int:
        """Verify-этап (как в pgadmin): фактические строки в цели против источника.

        Расхождение = source ≠ moved + rejected (потеряли/задвоили строки).
        Заодно сверяем реальный count в целевой таблице с ожидаемым moved.
        """
        from psycopg import sql

        mismatches = 0
        for entry in self.verify:
            schema, table = entry["table"].split(".", 1)
            target_count = conn.execute(
                sql.SQL("SELECT count(*) AS c FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table))
            ).fetchone()["c"]
            entry["target"] = int(target_count)
            accounted = entry["moved"] + entry["rejected"] == entry["source"]
            consistent = int(target_count) == entry["moved"]
            if not (accounted and consistent):
                mismatches += 1
        status = "passed" if mismatches == 0 else "failed"
        self._log("verify_rows", status, translate("migration.verify", self.locale, mismatches=mismatches))
        return mismatches

    def _reset_schemas(self, conn, schemas: list[str]) -> None:
        from psycopg import sql

        for schema in schemas:
            conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        self._log("reset_target", "passed", translate("migration.reset", self.locale))

    # -- Перенос одной таблицы ---------------------------------------------

    def _migrate_table(
        self,
        conn,
        prod_table: TableMetadata,
        dev_table: TableMetadata,
        source_rows: list[dict],
        parent_keys: dict[str, set],
        dev_enum_values: dict[str, set],
    ) -> tuple[int, int]:
        from psycopg import sql

        plans = self._column_plans(prod_table, dev_table, dev_enum_values)
        dev_columns = [plan.column.name for plan in plans]
        unique_cols = self._unique_columns(dev_table)
        fk = self._foreign_key(dev_table)

        seen_unique: set = set()
        to_insert: list[list] = []
        rejected: list[dict] = []
        key = f"{dev_table.schema_name}.{dev_table.name}"
        pk_cols = self._primary_key_columns(dev_table)

        for row in source_rows:
            values: dict[str, Any] = {}
            reason: str | None = None
            for plan in plans:
                raw = row.get(plan.source) if plan.source else None
                value, row_reason = self._transform(plan, raw)
                values[plan.column.name] = value
                reason = reason or row_reason

            if reason is None and unique_cols:
                signature = tuple(values[col] for col in unique_cols)
                if any(part is not None for part in signature) and signature in seen_unique:
                    reason = "duplicate_unique"
                else:
                    seen_unique.add(signature)

            if reason is None and fk is not None:
                ref_key, ref_columns, local_columns = fk
                referenced = parent_keys.get(ref_key, set())
                local_value = tuple(values.get(col) for col in local_columns)
                if all(part is not None for part in local_value) and local_value not in referenced:
                    reason = "orphan_foreign_key"

            if reason is not None:
                rejected.append({"row": row, "reason": reason})
                continue

            to_insert.append([values[name] for name in dev_columns])
            if pk_cols:
                parent_keys.setdefault(key, set()).add(tuple(values[col] for col in pk_cols))

        if to_insert:
            insert = sql.SQL("INSERT INTO {schema}.{table} ({cols}) VALUES ({ph})").format(
                schema=sql.Identifier(dev_table.schema_name),
                table=sql.Identifier(dev_table.name),
                cols=sql.SQL(", ").join(sql.Identifier(name) for name in dev_columns),
                ph=sql.SQL(", ").join(sql.Placeholder() * len(dev_columns)),
            )
            with conn.cursor() as cursor:
                cursor.executemany(insert, to_insert)

        self.verify.append({
            "table": f"{dev_table.schema_name}.{dev_table.name}",
            "source": len(source_rows),
            "moved": len(to_insert),
            "rejected": len(rejected),
        })
        self._log(
            f"load_{dev_table.name}",
            "passed",
            translate("migration.loaded", self.locale, schema=dev_table.schema_name, table=dev_table.name,
                      moved=len(to_insert), rejected=len(rejected)),
            rows_affected=len(to_insert),
        )
        return len(to_insert), len(rejected)

    # -- Планирование колонок ----------------------------------------------

    def _column_plans(
        self, prod_table: TableMetadata, dev_table: TableMetadata, dev_enum_values: dict[str, set]
    ) -> list[_ColumnPlan]:
        table_conflicts = self._conflicts_for(dev_table.schema_name, dev_table.name)
        rename_source = {}  # target_col -> source_col
        for conflict in table_conflicts:
            if conflict.category == "probable_column_rename" and "->" in conflict.column_name:
                src, dst = conflict.column_name.split("->", 1)
                rename_source[dst] = src

        plans: list[_ColumnPlan] = []
        for col in sorted(dev_table.columns.values(), key=lambda c: c.ordinal_position):
            name = col.name
            if name in prod_table.columns:
                source, kind = name, "direct"
            elif name in rename_source and rename_source[name] in prod_table.columns:
                source, kind = rename_source[name], "rename"
            else:
                source, kind = None, "added"

            plan = _ColumnPlan(column=col, source=source, kind=kind)
            for conflict in table_conflicts:
                if conflict.column_name in {name, f"{source}->{name}"}:
                    plan.categories.add(conflict.category)
                    if conflict.category == "varchar_length_reduction":
                        plan.varchar_limit = col.max_length
                    if conflict.category == "enum_value_mismatch":
                        prod_values = set(conflict.production_definition.get("enum_values", []))
                        dev_values = set(conflict.development_definition.get("enum_values", []))
                        plan.removed_enum = prod_values - dev_values
                        plan.allowed_enum = dev_values
            plan.allowed_enum |= dev_enum_values.get(col.normalized_type, set())
            plan.enum_mapping = dict(self.action_params.get("map_enum_values", {}).get("mapping", {}))
            plan.default_value = self._default_for(col)
            plans.append(plan)
        return plans

    def _transform(self, plan: _ColumnPlan, raw: Any) -> tuple[Any, str | None]:
        col = plan.column

        if plan.kind == "added":
            return plan.default_value, None

        # Восстановление NOT NULL: пустое значение заменяем дефолтом.
        if raw is None:
            if not col.nullable:
                return plan.default_value, None
            return None, None

        text = str(raw)

        if {"incompatible_type_change"} & plan.categories or col.normalized_type == "numeric" and plan.source and self._needs_numeric(plan):
            if not NUMERIC_RE.match(text):
                return None, "invalid_numeric"
        if {"text_to_integer"} & plan.categories:
            if not INTEGER_RE.match(text):
                return None, "invalid_integer"

        if plan.varchar_limit and len(text) > plan.varchar_limit:
            text = text[: plan.varchar_limit]
            return text, None

        if plan.removed_enum and text in plan.removed_enum:
            mapped = plan.enum_mapping.get(text)
            if mapped and mapped in plan.allowed_enum:
                return mapped, None
            return None, "unsupported_enum_value"

        return raw, None

    def _needs_numeric(self, plan: _ColumnPlan) -> bool:
        return "incompatible_type_change" in plan.categories

    # -- Ограничения и индексы (валидация постфактум) -----------------------

    def _apply_constraints_and_indexes(self, conn, dev: SchemaSnapshot, ordered: list[str]) -> int:
        failures = 0
        for key in ordered:
            table = dev.tables[key]
            for name, statement in ddl_builder.constraint_statements(table, kinds=("primary_key", "unique", "check")):
                failures += self._guarded(conn, name, statement)
        for key in ordered:  # FK — после всех PK/unique
            table = dev.tables[key]
            for name, statement in ddl_builder.constraint_statements(table, kinds=("foreign_key",)):
                failures += self._guarded(conn, name, statement)
        for key in ordered:
            table = dev.tables[key]
            for name, statement in ddl_builder.index_statements(table):
                failures += self._guarded(conn, name, statement, is_text=True)
        status = "passed" if failures == 0 else "failed"
        self._log("validate_constraints", status,
                  translate("migration.validation", self.locale, failures=failures))
        return failures

    def _apply_schema_objects(self, conn, dev: SchemaSnapshot, schema_set: set) -> int:
        """Накатить функции/процедуры, представления и триггеры (после таблиц)."""
        failures = 0
        count = 0
        for name, statement in ddl_builder.routine_statements(dev, schema_set):
            failures += self._guarded(conn, name, statement, is_text=True)
            count += 1
        for name, statement in ddl_builder.view_statements(dev, schema_set):
            failures += self._guarded(conn, name, statement)
            count += 1
        for name, statement in ddl_builder.trigger_statements(dev, schema_set):
            failures += self._guarded(conn, name, statement, is_text=True)
            count += 1
        if count:
            self._log(
                "apply_objects",
                "passed" if failures == 0 else "failed",
                translate("migration.objects", self.locale, count=count, failures=failures),
            )
        return failures

    def _guarded(self, conn, name: str, statement, *, is_text: bool = False) -> int:
        """Выполнить DDL в savepoint; ошибка — это валидационный провал, не крах."""
        try:
            with conn.transaction():
                conn.execute(statement if not is_text else statement)
            return 0
        except Exception as exc:
            self._log(f"constraint_{name}", "failed",
                      translate("migration.constraint_failed", self.locale, name=name, error=str(exc)))
            return 1

    # -- Топосорт по внешним ключам ----------------------------------------

    def _topo_sort(self, dev: SchemaSnapshot) -> list[str]:
        deps: dict[str, set[str]] = {key: set() for key in dev.tables}
        for key, table in dev.tables.items():
            for constraint in table.constraints:
                if constraint.constraint_type == "foreign_key" and constraint.referenced_table:
                    ref_schema = constraint.referenced_schema or table.schema_name
                    ref_key = f"{ref_schema}.{constraint.referenced_table}"
                    if ref_key in deps and ref_key != key:
                        deps[key].add(ref_key)
        ordered: list[str] = []
        visited: set[str] = set()
        temp: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in temp:  # цикл — рвём, порядок в целом сохраняем
                return
            temp.add(node)
            for dep in sorted(deps.get(node, set())):
                visit(dep)
            temp.discard(node)
            visited.add(node)
            ordered.append(node)

        for key in sorted(dev.tables):
            visit(key)
        return ordered

    # -- Вспомогательное ----------------------------------------------------

    def _conflicts_for(self, schema: str, table: str):
        return [
            conflict
            for conflict in self.analysis.conflicts.all()
            if conflict.schema_name == schema and conflict.table_name == table
        ]

    def _unique_columns(self, table: TableMetadata) -> list[str]:
        for constraint in table.constraints:
            if constraint.constraint_type == "unique":
                return list(constraint.columns)
        return []

    def _primary_key_columns(self, table: TableMetadata) -> list[str]:
        for constraint in table.constraints:
            if constraint.constraint_type == "primary_key":
                return list(constraint.columns)
        return []

    def _foreign_key(self, table: TableMetadata):
        for constraint in table.constraints:
            if constraint.constraint_type == "foreign_key" and constraint.referenced_table:
                ref_schema = constraint.referenced_schema or table.schema_name
                ref_key = f"{ref_schema}.{constraint.referenced_table}"
                return ref_key, list(constraint.referenced_columns), list(constraint.columns)
        return None

    def _default_for(self, col: ColumnMetadata) -> Any:
        backfill = self.action_params.get("backfill_null_with_default", {})
        if backfill.get("column") == col.name and "default_value" in backfill:
            return backfill["default_value"]
        nt = col.normalized_type
        if nt in _INT_TYPES or nt == "numeric":
            return 0
        if nt == "boolean":
            return False
        if nt in {"varchar", "text"}:
            return ""
        if nt in {"timestamptz", "timestamp"}:
            from django.utils import timezone
            return timezone.now()
        return ""

    # -- Логи и финализация -------------------------------------------------

    def _log(self, step: str, status: str, message: str, rows_affected: int = 0, sql_preview: str = "") -> None:
        self.sequence += 1
        self.logs.append({
            "sequence": self.sequence,
            "step": step,
            "status": status,
            "message": message,
            "rows_affected": int(rows_affected or 0),
            "sql_preview": sql_preview,
        })

    def _finish(self, result: MigrationResult) -> MigrationResult:
        result.logs = self.logs
        status = AnalysisRun.DryRunStatus.PASSED if result.passed else AnalysisRun.DryRunStatus.FAILED
        target_label = self.target_profile.database if self.target_profile is not None else translate("migration.isolated_target", self.locale)
        report = {
            **(self.analysis.report or {}),
            "migrationStatus": translate("migration.passed" if result.passed else "migration.failed", self.locale),
            "transferredRows": result.transferred_rows,
            "rejectedRows": result.rejected_rows,
            "validationFailures": result.validation_failures,
            "rowMismatches": result.row_mismatches,
            "verify": result.verify,
            "migrationTarget": target_label,
            "migrationLimitation": translate("migration.limitation", self.locale),
            "logs": result.logs,
        }
        with transaction.atomic():
            self.analysis.dry_run_status = status
            self.analysis.report = report
            metrics = dict(self.analysis.metrics or {})
            metrics.update({
                "dryRunStatus": status,
                "transferredRows": result.transferred_rows,
                "rejectedRows": result.rejected_rows,
                "validationFailures": result.validation_failures,
                "rowMismatches": result.row_mismatches,
            })
            self.analysis.metrics = metrics
            self.analysis.save(update_fields=["dry_run_status", "report", "metrics", "updated_at"])
            DryRunLog.objects.filter(analysis=self.analysis).delete()
            for entry in self.logs:
                DryRunLog.objects.create(analysis=self.analysis, **entry)
        return result
