from __future__ import annotations

from typing import Any, Sequence

from psycopg import sql

from .types import PreflightEvidence

NUMERIC_TEXT_RE = r"^\s*[+-]?((\d+(\.\d+)?)|(\.\d+))\s*$"
INTEGER_TEXT_RE = r"^\s*[+-]?\d+\s*$"


def validate_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier or "\x00" in identifier:
        raise ValueError("PostgreSQL identifiers must be non-empty strings without NUL characters.")
    return identifier


def ident(name: str) -> sql.Identifier:
    return sql.Identifier(validate_identifier(name))


def table_ident(schema: str, table: str) -> sql.Composed:
    return sql.SQL(".").join([ident(schema), ident(table)])


def preview_identifier(identifier: str) -> str:
    return '"' + validate_identifier(identifier).replace('"', '""') + '"'


def preview_table(table: str, schema: str = "public") -> str:
    return f"{preview_identifier(schema)}.{preview_identifier(table)}"


def unsupported_preflight(reason: str, *, sql_preview: str = "") -> PreflightEvidence:
    return PreflightEvidence(status="unsupported_preflight", explanation=reason, sql_preview=sql_preview)


class PreflightRunner:
    def __init__(self, conn, *, sample_limit: int = 5):
        self.conn = conn
        self.sample_limit = min(max(int(sample_limit), 1), 20)

    def nullable_to_not_null(self, schema: str, table: str, column: str) -> PreflightEvidence:
        where = sql.SQL("{column} IS NULL").format(column=ident(column))
        return self._count_and_sample(schema, table, [column], where, explanation="Rows containing NULL cannot satisfy NOT NULL.")

    def incompatible_type_to_numeric(self, schema: str, table: str, column: str) -> PreflightEvidence:
        where = sql.SQL("{column} IS NOT NULL AND NOT ({column}::text ~ %s)").format(column=ident(column))
        return self._count_and_sample(
            schema,
            table,
            [column],
            where,
            (NUMERIC_TEXT_RE,),
            explanation="Text values that do not match the numeric pattern cannot be cast safely.",
        )

    def text_to_integer(self, schema: str, table: str, column: str) -> PreflightEvidence:
        where = sql.SQL("{column} IS NOT NULL AND NOT ({column}::text ~ %s)").format(column=ident(column))
        return self._count_and_sample(
            schema,
            table,
            [column],
            where,
            (INTEGER_TEXT_RE,),
            explanation="Text values that do not match the integer pattern cannot be cast safely.",
        )

    def varchar_length_reduction(self, schema: str, table: str, column: str, max_length: int) -> PreflightEvidence:
        where = sql.SQL("{column} IS NOT NULL AND char_length({column}::text) > %s").format(column=ident(column))
        return self._count_and_sample(
            schema,
            table,
            [column],
            where,
            (int(max_length),),
            explanation=f"Values longer than {max_length} characters will not fit the development column.",
        )

    def enum_mismatch(self, schema: str, table: str, column: str, allowed_values: Sequence[str]) -> PreflightEvidence:
        where = sql.SQL("{column} IS NOT NULL AND NOT ({column}::text = ANY(%s))").format(column=ident(column))
        result = self._count_and_sample(
            schema,
            table,
            [column],
            where,
            (list(allowed_values),),
            explanation="Production rows use enum values absent from development.",
        )
        result.evidence["allowed_development_values"] = list(allowed_values)
        return result

    def foreign_key_orphans(
        self,
        schema: str,
        table: str,
        columns: Sequence[str],
        referenced_schema: str,
        referenced_table: str,
        referenced_columns: Sequence[str],
    ) -> PreflightEvidence:
        if not columns or len(columns) != len(referenced_columns):
            return unsupported_preflight("Foreign-key columns could not be paired safely for preflight.")
        non_null = sql.SQL(" AND ").join(sql.SQL("t.{column} IS NOT NULL").format(column=ident(column)) for column in columns)
        matches = sql.SQL(" AND ").join(
            sql.SQL("r.{ref_column} = t.{column}").format(ref_column=ident(ref_column), column=ident(column))
            for column, ref_column in zip(columns, referenced_columns, strict=True)
        )
        where = non_null + sql.SQL(" AND NOT EXISTS (SELECT 1 FROM {ref_table} r WHERE ").format(
            ref_table=table_ident(referenced_schema, referenced_table)
        ) + matches + sql.SQL(")")
        result = self._count_and_sample(
            schema,
            table,
            list(columns),
            where,
            explanation="Production rows reference keys that do not exist in the referenced production table.",
            alias="t",
        )
        result.evidence.update(
            {
                "referenced_schema": referenced_schema,
                "referenced_table": referenced_table,
                "referenced_columns": list(referenced_columns),
            }
        )
        return result

    def unique_duplicates(self, schema: str, table: str, columns: Sequence[str]) -> PreflightEvidence:
        if not columns:
            return unsupported_preflight("The unique constraint has no inspectable columns.")
        column_list = sql.SQL(", ").join(ident(column) for column in columns)
        non_null = sql.SQL(" AND ").join(sql.SQL("{column} IS NOT NULL").format(column=ident(column)) for column in columns)
        count_query = sql.SQL(
            "SELECT COALESCE(sum(duplicate_count), 0) AS count FROM ("
            "SELECT count(*) AS duplicate_count FROM {table} WHERE {non_null} GROUP BY {columns} HAVING count(*) > 1"
            ") d"
        ).format(table=table_ident(schema, table), columns=column_list, non_null=non_null)
        sample_query = sql.SQL(
            "SELECT json_build_object('values', json_build_array({columns}), 'count', count(*)) AS value "
            "FROM {table} WHERE {non_null} GROUP BY {columns} HAVING count(*) > 1 LIMIT %s"
        ).format(table=table_ident(schema, table), columns=column_list, non_null=non_null)
        count = self.conn.execute(count_query).fetchone()["count"]
        samples = self.conn.execute(sample_query, (self.sample_limit,)).fetchall()
        return PreflightEvidence(
            affected_row_count=int(count),
            sample_values=[row["value"] for row in samples],
            evidence={"columns": list(columns)},
            status="checked",
            explanation="Duplicate value groups cannot satisfy the new unique constraint.",
            sql_preview=f"-- Read-only duplicate check on {preview_table(table, schema)}",
        )

    def probable_rename(self, schema: str, table: str, source_column: str, target_column: str) -> PreflightEvidence:
        where = sql.SQL("{column} IS NOT NULL").format(column=ident(source_column))
        result = self._count_and_sample(
            schema,
            table,
            [source_column],
            where,
            explanation="Non-null source values would need an explicit mapping to the renamed column.",
        )
        result.evidence.update({"source_column": source_column, "target_column": target_column, "confidence": "heuristic"})
        return result

    def _count_and_sample(
        self,
        schema: str,
        table: str,
        columns: Sequence[str],
        where: sql.Composable,
        params: tuple[Any, ...] = (),
        *,
        explanation: str,
        alias: str = "",
    ) -> PreflightEvidence:
        table_sql = table_ident(schema, table)
        alias_sql = sql.SQL(" ") + ident(alias) if alias else sql.SQL("")
        count_query = sql.SQL("SELECT count(*) AS count FROM {table}{alias} WHERE ").format(table=table_sql, alias=alias_sql) + where
        sample_columns = sql.SQL(", ").join(
            sql.SQL("{prefix}{column}::text").format(prefix=sql.SQL(f"{alias}.") if alias else sql.SQL(""), column=ident(column))
            for column in columns
        )
        sample_query = (
            sql.SQL("SELECT json_build_array({columns}) AS value FROM {table}{alias} WHERE ").format(
                columns=sample_columns,
                table=table_sql,
                alias=alias_sql,
            )
            + where
            + sql.SQL(" LIMIT %s")
        )
        count = self.conn.execute(count_query, params).fetchone()["count"]
        samples = self.conn.execute(sample_query, (*params, self.sample_limit)).fetchall()
        return PreflightEvidence(
            affected_row_count=int(count),
            sample_values=[row["value"][0] if len(row["value"]) == 1 else row["value"] for row in samples],
            evidence={"columns": list(columns)},
            status="checked",
            explanation=explanation,
            sql_preview=f"-- Read-only affected-row check on {preview_table(table, schema)}",
        )


def render_preflight_preview(category: str, table: str, column: str = "", schema: str = "public") -> str:
    base = preview_table(table, schema)
    if category == "nullable_to_not_null":
        return f"SELECT count(*) FROM {base} WHERE {preview_identifier(column)} IS NULL;"
    if category in {"incompatible_type_change", "text_to_integer"}:
        return f"SELECT count(*) FROM {base} WHERE {preview_identifier(column)} IS NOT NULL AND NOT ({preview_identifier(column)}::text ~ '<validated-pattern>');"
    if category == "varchar_length_reduction":
        return f"SELECT count(*) FROM {base} WHERE char_length({preview_identifier(column)}::text) > <new-limit>;"
    if category == "enum_value_mismatch":
        return f"SELECT count(*) FROM {base} WHERE {preview_identifier(column)}::text NOT IN (<development-enum-values>);"
    return f"-- No executable preflight template for {category}"
