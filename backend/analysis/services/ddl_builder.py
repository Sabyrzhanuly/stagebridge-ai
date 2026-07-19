"""Генерация DDL целевой схемы из dev-снапшота.

Накат создаёт изолированную копию development-схемы в управляемой БД, поэтому
DDL строится детерминированно из :class:`SchemaSnapshot`, без обращения к
исходным базам и без произвольного SQL. Все идентификаторы проходят через
``psycopg.sql``; числовые модификаторы типов берутся из каталога (int из БД),
поэтому инъекции невозможны.
"""

from __future__ import annotations

from psycopg import sql

from .types import ColumnMetadata, EnumMetadata, SchemaSnapshot, TableMetadata

# Скалярные типы, которые PostgreSQL принимает как есть (по нормализованному имени).
SCALAR_TYPES = {
    "integer",
    "bigint",
    "smallint",
    "text",
    "boolean",
    "date",
    "uuid",
    "json",
    "jsonb",
    "timestamptz",
    "timestamp",
    "time",
    "timetz",
    "real",
    "double precision",
    "bytea",
    "inet",
    "cidr",
}


def _enum_lookup(snapshot: SchemaSnapshot) -> dict[str, EnumMetadata]:
    """Enum по «голому» имени типа — так на него ссылается ``normalized_type``."""
    return {enum.name: enum for enum in snapshot.enums.values()}


def column_type_sql(column: ColumnMetadata, enums: dict[str, EnumMetadata]) -> sql.Composable:
    """Собрать SQL-тип колонки, восстанавливая длину/точность и enum-квалификацию."""
    enum = enums.get(column.normalized_type)
    if enum is not None:
        return sql.SQL("{}.{}").format(sql.Identifier(enum.schema_name), sql.Identifier(enum.name))

    nt = column.normalized_type
    if nt == "varchar":
        if column.max_length:
            return sql.SQL("varchar({})").format(sql.Literal(int(column.max_length)))
        return sql.SQL("varchar")
    if nt == "numeric":
        if column.numeric_precision:
            return sql.SQL("numeric({}, {})").format(
                sql.Literal(int(column.numeric_precision)),
                sql.Literal(int(column.numeric_scale or 0)),
            )
        return sql.SQL("numeric")
    if nt in SCALAR_TYPES:
        return sql.SQL(nt)  # nt приходит из нашего же нормализатора, не из пользователя
    # Последний рубеж: сырой data_type из information_schema — валидное SQL-имя типа.
    return sql.SQL(column.data_type)


def create_schema_statements(snapshot: SchemaSnapshot, schemas: list[str]) -> list[sql.Composable]:
    """CREATE SCHEMA для всех целевых схем, кроме public (public создаётся при reset)."""
    statements: list[sql.Composable] = []
    for schema in schemas:
        if schema == "public":
            continue
        statements.append(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
    return statements


def create_enum_statements(snapshot: SchemaSnapshot, schemas: set[str]) -> list[sql.Composable]:
    statements: list[sql.Composable] = []
    for enum in snapshot.enums.values():
        if enum.schema_name not in schemas:
            continue
        values = sql.SQL(", ").join(sql.Literal(value) for value in enum.values)
        statements.append(
            sql.SQL("CREATE TYPE {}.{} AS ENUM ({})").format(
                sql.Identifier(enum.schema_name), sql.Identifier(enum.name), values
            )
        )
    return statements


def create_sequence_statements(snapshot: SchemaSnapshot, schemas: set[str]) -> list[sql.Composable]:
    statements: list[sql.Composable] = []
    for seq in snapshot.sequences:
        if seq.schema_name not in schemas:
            continue
        stmt = sql.SQL("CREATE SEQUENCE IF NOT EXISTS {}.{}").format(
            sql.Identifier(seq.schema_name), sql.Identifier(seq.name)
        )
        if seq.increment:
            stmt = stmt + sql.SQL(" INCREMENT {}").format(sql.Literal(int(seq.increment)))
        if seq.start_value:
            stmt = stmt + sql.SQL(" START {}").format(sql.Literal(int(seq.start_value)))
        statements.append(stmt)
    return statements


def create_table_statement(table: TableMetadata, enums: dict[str, EnumMetadata]) -> sql.Composable:
    """CREATE TABLE только со столбцами (constraints добавляются отдельно, после загрузки)."""
    columns = sorted(table.columns.values(), key=lambda col: col.ordinal_position)
    column_defs = []
    for col in columns:
        piece = sql.SQL("{} {}").format(sql.Identifier(col.name), column_type_sql(col, enums))
        if not col.nullable:
            piece = piece + sql.SQL(" NOT NULL")
        column_defs.append(piece)
    return sql.SQL("CREATE TABLE {}.{} ({})").format(
        sql.Identifier(table.schema_name),
        sql.Identifier(table.name),
        sql.SQL(", ").join(column_defs),
    )


def constraint_statements(
    table: TableMetadata, *, kinds: tuple[str, ...]
) -> list[tuple[str, sql.Composable]]:
    """ALTER TABLE ADD CONSTRAINT для указанных типов, используя pg-определение."""
    statements: list[tuple[str, sql.Composable]] = []
    for constraint in table.constraints:
        if constraint.constraint_type not in kinds:
            continue
        statements.append(
            (
                constraint.name,
                sql.SQL("ALTER TABLE {}.{} ADD CONSTRAINT {} ").format(
                    sql.Identifier(table.schema_name),
                    sql.Identifier(table.name),
                    sql.Identifier(constraint.name),
                )
                + sql.SQL(constraint.definition),  # определение из pg_get_constraintdef
            )
        )
    return statements


def routine_statements(snapshot: SchemaSnapshot, schemas: set[str]) -> list[tuple[str, str]]:
    """CREATE-определения функций/процедур (pg_get_functiondef самодостаточен)."""
    out: list[tuple[str, str]] = []
    for routine in snapshot.routines.values():
        if routine.schema_name in schemas and routine.definition:
            out.append((f"{routine.schema_name}.{routine.name}", routine.definition))
    return out


def view_statements(snapshot: SchemaSnapshot, schemas: set[str]) -> list[tuple[str, sql.Composable]]:
    out: list[tuple[str, sql.Composable]] = []
    for view in snapshot.views.values():
        if view.schema_name not in schemas or not view.definition:
            continue
        keyword = "CREATE MATERIALIZED VIEW " if view.materialized else "CREATE VIEW "
        body = view.definition.rstrip().rstrip(";")
        stmt = sql.SQL(keyword + "{}.{} AS ").format(sql.Identifier(view.schema_name), sql.Identifier(view.name)) + sql.SQL(body)
        out.append((f"{view.schema_name}.{view.name}", stmt))
    return out


def trigger_statements(snapshot: SchemaSnapshot, schemas: set[str]) -> list[tuple[str, str]]:
    """CREATE TRIGGER-определения (pg_get_triggerdef самодостаточен)."""
    out: list[tuple[str, str]] = []
    for trigger in snapshot.triggers.values():
        if trigger.schema_name in schemas and trigger.definition:
            out.append((f"{trigger.schema_name}.{trigger.name}", trigger.definition))
    return out


def index_statements(table: TableMetadata) -> list[tuple[str, str]]:
    """Индексы (кроме тех, что стоят за PK/unique-ограничениями) как готовый DDL-текст."""
    constraint_names = {c.name for c in table.constraints if c.constraint_type in {"primary_key", "unique"}}
    result: list[tuple[str, str]] = []
    for index in table.indexes:
        if index.name in constraint_names:
            continue
        result.append((index.name, index.definition))
    return result
