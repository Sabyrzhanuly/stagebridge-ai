from __future__ import annotations

from collections import defaultdict
from typing import Any

from .types import (
    ColumnMetadata,
    ConstraintMetadata,
    EnumMetadata,
    IndexMetadata,
    RoutineMetadata,
    SchemaSnapshot,
    SequenceMetadata,
    TableMetadata,
    TriggerMetadata,
    ViewMetadata,
)

SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")


def normalize_type(row: dict[str, Any]) -> str:
    data_type = str(row.get("data_type") or "").lower()
    udt_name = str(row.get("udt_name") or "").lower()
    if data_type == "user-defined" and udt_name:
        return udt_name
    if data_type in {"character varying", "varchar"}:
        return "varchar"
    if data_type in {"numeric", "decimal"}:
        return "numeric"
    if data_type in {"integer", "int4"}:
        return "integer"
    if data_type in {"bigint", "int8"}:
        return "bigint"
    if data_type in {"text"}:
        return "text"
    return udt_name or data_type


class SchemaInspector:
    def __init__(
        self,
        conn,
        database_name: str,
        *,
        selected_schemas: list[str] | None = None,
        ignored_tables: list[str] | None = None,
    ):
        self.conn = conn
        self.database_name = database_name
        self.selected_schemas = selected_schemas or []
        self.ignored_tables = {name.strip() for name in (ignored_tables or []) if name.strip()}

    def inspect(self) -> SchemaSnapshot:
        schemas = self._schemas()
        tables = self._tables()
        columns = self._columns()
        constraints = self._constraints()
        indexes = self._indexes()
        enums = self._enums()
        sequences = self._sequences()

        table_map: dict[str, TableMetadata] = {}
        for row in tables:
            if self._table_ignored(row["table_schema"], row["table_name"]):
                continue
            key = self._table_key(row["table_schema"], row["table_name"])
            table_map[key] = TableMetadata(schema_name=row["table_schema"], name=row["table_name"])

        for row in columns:
            key = self._table_key(row["table_schema"], row["table_name"])
            if key not in table_map:
                continue
            column = ColumnMetadata(
                schema_name=row["table_schema"],
                table_name=row["table_name"],
                name=row["column_name"],
                ordinal_position=row["ordinal_position"],
                data_type=row["data_type"],
                normalized_type=normalize_type(row),
                nullable=row["is_nullable"] == "YES",
                default=row["column_default"],
                max_length=row["character_maximum_length"],
                numeric_precision=row["numeric_precision"],
                numeric_scale=row["numeric_scale"],
            )
            table_map[key].columns[column.name] = column

        for constraint in constraints:
            key = self._table_key(constraint.schema_name, constraint.table_name)
            if key in table_map:
                table_map[key].constraints.append(constraint)

        for index in indexes:
            key = self._table_key(index.schema_name, index.table_name)
            if key in table_map:
                table_map[key].indexes.append(index)

        return SchemaSnapshot(
            database_name=self.database_name,
            schemas=schemas,
            tables=table_map,
            enums={f"{enum.schema_name}.{enum.name}": enum for enum in enums},
            sequences=sequences,
            routines={f"{r.schema_name}.{r.name}({r.identity_args})": r for r in self._routines()},
            views={f"{v.schema_name}.{v.name}": v for v in self._views()},
            triggers={f"{t.schema_name}.{t.table_name}.{t.name}": t for t in self._triggers()},
        )

    @staticmethod
    def _table_key(schema: str, table: str) -> str:
        return f"{schema}.{table}"

    def _table_ignored(self, schema: str, table: str) -> bool:
        return table in self.ignored_tables or f"{schema}.{table}" in self.ignored_tables

    def _schema_params(self) -> tuple[bool, list[str]]:
        return (not self.selected_schemas, self.selected_schemas)

    def _schemas(self) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name <> ALL(%s)
              AND schema_name NOT LIKE 'pg_temp_%%'
              AND schema_name NOT LIKE 'pg_toast_temp_%%'
              AND (%s OR schema_name = ANY(%s))
            ORDER BY schema_name
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        return [row["schema_name"] for row in rows]

    def _tables(self) -> list[dict[str, Any]]:
        return self.conn.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema <> ALL(%s)
              AND table_type = 'BASE TABLE'
              AND (%s OR table_schema = ANY(%s))
            ORDER BY table_schema, table_name
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()

    def _columns(self) -> list[dict[str, Any]]:
        return self.conn.execute(
            """
            SELECT table_schema, table_name, column_name, ordinal_position, is_nullable,
                   data_type, udt_name, column_default, character_maximum_length,
                   numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema <> ALL(%s)
              AND (%s OR table_schema = ANY(%s))
            ORDER BY table_schema, table_name, ordinal_position
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()

    def _constraints(self) -> list[ConstraintMetadata]:
        rows = self.conn.execute(
            """
            SELECT
              ns.nspname AS table_schema,
              cl.relname AS table_name,
              con.conname AS constraint_name,
              con.contype AS constraint_type,
              pg_get_constraintdef(con.oid, true) AS definition,
              COALESCE((
                SELECT array_agg(att.attname ORDER BY u.ord)
                FROM unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord)
                JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = u.attnum
              ), ARRAY[]::text[]) AS columns,
              ref_ns.nspname AS referenced_schema,
              ref_cl.relname AS referenced_table,
              COALESCE((
                SELECT array_agg(att.attname ORDER BY u.ord)
                FROM unnest(con.confkey) WITH ORDINALITY AS u(attnum, ord)
                JOIN pg_attribute att ON att.attrelid = con.confrelid AND att.attnum = u.attnum
              ), ARRAY[]::text[]) AS referenced_columns
            FROM pg_constraint con
            JOIN pg_class cl ON cl.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = cl.relnamespace
            LEFT JOIN pg_class ref_cl ON ref_cl.oid = con.confrelid
            LEFT JOIN pg_namespace ref_ns ON ref_ns.oid = ref_cl.relnamespace
            WHERE ns.nspname <> ALL(%s)
              AND cl.relkind IN ('r', 'p')
              AND (%s OR ns.nspname = ANY(%s))
            ORDER BY ns.nspname, cl.relname, con.conname
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        type_map = {"p": "primary_key", "f": "foreign_key", "u": "unique", "c": "check"}
        return [
            ConstraintMetadata(
                schema_name=row["table_schema"],
                table_name=row["table_name"],
                name=row["constraint_name"],
                constraint_type=type_map.get(row["constraint_type"], "other"),
                columns=list(row["columns"] or []),
                definition=row["definition"],
                referenced_schema=row["referenced_schema"],
                referenced_table=row["referenced_table"],
                referenced_columns=list(row["referenced_columns"] or []),
            )
            for row in rows
        ]

    def _indexes(self) -> list[IndexMetadata]:
        rows = self.conn.execute(
            """
            SELECT schemaname AS schema_name, tablename AS table_name, indexname AS index_name, indexdef AS definition
            FROM pg_indexes
            WHERE schemaname <> ALL(%s)
              AND (%s OR schemaname = ANY(%s))
            ORDER BY schemaname, tablename, indexname
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        return [
            IndexMetadata(
                schema_name=row["schema_name"],
                table_name=row["table_name"],
                name=row["index_name"],
                definition=row["definition"],
            )
            for row in rows
        ]

    def _enums(self) -> list[EnumMetadata]:
        rows = self.conn.execute(
            """
            SELECT n.nspname AS schema_name, t.typname AS enum_name, e.enumlabel AS enum_value, e.enumsortorder
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname <> ALL(%s)
              AND (%s OR n.nspname = ANY(%s))
            ORDER BY n.nspname, t.typname, e.enumsortorder
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for row in rows:
            grouped[(row["schema_name"], row["enum_name"])].append(row["enum_value"])
        return [EnumMetadata(schema_name=schema, name=name, values=values) for (schema, name), values in grouped.items()]

    def _sequences(self) -> list[SequenceMetadata]:
        rows = self.conn.execute(
            """
            SELECT sequence_schema, sequence_name, data_type, start_value, increment
            FROM information_schema.sequences
            WHERE sequence_schema <> ALL(%s)
              AND (%s OR sequence_schema = ANY(%s))
            ORDER BY sequence_schema, sequence_name
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        return [
            SequenceMetadata(
                schema_name=row["sequence_schema"],
                name=row["sequence_name"],
                data_type=row["data_type"],
                start_value=str(row["start_value"]) if row["start_value"] is not None else None,
                increment=str(row["increment"]) if row["increment"] is not None else None,
            )
            for row in rows
        ]

    def _routines(self) -> list[RoutineMetadata]:
        """Хранимые функции и процедуры (без объектов расширений)."""
        rows = self.conn.execute(
            """
            SELECT n.nspname AS schema_name, p.proname AS name,
                   pg_get_function_identity_arguments(p.oid) AS identity_args,
                   CASE p.prokind WHEN 'p' THEN 'procedure' ELSE 'function' END AS kind,
                   pg_get_functiondef(p.oid) AS definition
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname <> ALL(%s)
              AND p.prokind IN ('f', 'p')
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
              AND (%s OR n.nspname = ANY(%s))
            ORDER BY n.nspname, p.proname
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        return [
            RoutineMetadata(
                schema_name=row["schema_name"],
                name=row["name"],
                identity_args=row["identity_args"] or "",
                kind=row["kind"],
                definition=row["definition"] or "",
            )
            for row in rows
        ]

    def _views(self) -> list[ViewMetadata]:
        rows = self.conn.execute(
            """
            SELECT schemaname AS schema_name, viewname AS name, definition, false AS materialized
            FROM pg_views
            WHERE schemaname <> ALL(%s) AND (%s OR schemaname = ANY(%s))
            UNION ALL
            SELECT schemaname AS schema_name, matviewname AS name, definition, true AS materialized
            FROM pg_matviews
            WHERE schemaname <> ALL(%s) AND (%s OR schemaname = ANY(%s))
            ORDER BY 1, 2
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params(), list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        return [
            ViewMetadata(
                schema_name=row["schema_name"],
                name=row["name"],
                materialized=bool(row["materialized"]),
                definition=(row["definition"] or "").strip(),
            )
            for row in rows
        ]

    def _triggers(self) -> list[TriggerMetadata]:
        rows = self.conn.execute(
            """
            SELECT n.nspname AS schema_name, c.relname AS table_name, t.tgname AS name,
                   pg_get_triggerdef(t.oid) AS definition
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE NOT t.tgisinternal
              AND n.nspname <> ALL(%s)
              AND (%s OR n.nspname = ANY(%s))
            ORDER BY n.nspname, c.relname, t.tgname
            """,
            (list(SYSTEM_SCHEMAS), *self._schema_params()),
        ).fetchall()
        return [
            TriggerMetadata(
                schema_name=row["schema_name"],
                table_name=row["table_name"],
                name=row["name"],
                definition=row["definition"] or "",
            )
            for row in rows
        ]
