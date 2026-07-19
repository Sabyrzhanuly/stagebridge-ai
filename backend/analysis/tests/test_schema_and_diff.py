from __future__ import annotations

from analysis.services.diff_engine import detect_conflicts
from analysis.services.schema_inspector import normalize_type
from analysis.services.types import ColumnMetadata, ConstraintMetadata, EnumMetadata, IndexMetadata, PreflightEvidence, SchemaSnapshot, SequenceMetadata, TableMetadata


def column(table: str, name: str, typ: str, nullable: bool = True, ordinal: int = 1) -> ColumnMetadata:
    return ColumnMetadata(
        schema_name="public",
        table_name=table,
        name=name,
        ordinal_position=ordinal,
        data_type="USER-DEFINED" if typ == "order_status" else typ,
        normalized_type=typ,
        nullable=nullable,
    )


def snapshot_prod() -> SchemaSnapshot:
    users = TableMetadata(
        schema_name="public",
        name="users",
        columns={
            "id": column("users", "id", "integer", False),
            "email": column("users", "email", "varchar", True),
            "phone": column("users", "phone", "varchar", True),
        },
        constraints=[ConstraintMetadata(schema_name="public", table_name="users", name="users_pkey", constraint_type="primary_key", columns=["id"], definition="PRIMARY KEY (id)")],
    )
    customer = TableMetadata(
        schema_name="public",
        name="customer",
        columns={"id": column("customer", "id", "integer", False), "full_name": column("customer", "full_name", "varchar", True)},
    )
    orders = TableMetadata(
        schema_name="public",
        name="orders",
        columns={
            "id": column("orders", "id", "integer", False),
            "customer_id": column("orders", "customer_id", "integer", True),
            "price": column("orders", "price", "varchar", True),
            "status": column("orders", "status", "order_status", False),
        },
    )
    return SchemaSnapshot(
        database_name="prod",
        schemas=["public"],
        tables={"public.users": users, "public.customer": customer, "public.orders": orders},
        enums={"public.order_status": EnumMetadata(schema_name="public", name="order_status", values=["pending", "paid", "cancelled"])},
        sequences=[],
    )


def snapshot_dev() -> SchemaSnapshot:
    users = TableMetadata(
        schema_name="public",
        name="users",
        columns={
            "id": column("users", "id", "integer", False),
            "email": column("users", "email", "varchar", True),
            "phone": column("users", "phone", "varchar", False),
        },
        constraints=[
            ConstraintMetadata(schema_name="public", table_name="users", name="users_pkey", constraint_type="primary_key", columns=["id"], definition="PRIMARY KEY (id)"),
            ConstraintMetadata(schema_name="public", table_name="users", name="users_email_unique", constraint_type="unique", columns=["email"], definition="UNIQUE (email)"),
        ],
    )
    customer = TableMetadata(
        schema_name="public",
        name="customer",
        columns={"id": column("customer", "id", "integer", False), "display_name": column("customer", "display_name", "varchar", False)},
    )
    orders = TableMetadata(
        schema_name="public",
        name="orders",
        columns={
            "id": column("orders", "id", "integer", False),
            "customer_id": column("orders", "customer_id", "integer", True),
            "price": column("orders", "price", "numeric", True),
            "status": column("orders", "status", "order_status", False),
        },
        constraints=[
            ConstraintMetadata(schema_name="public", table_name="orders", name="orders_customer_fk", constraint_type="foreign_key", columns=["customer_id"], referenced_table="customer", referenced_columns=["id"], definition="FOREIGN KEY (customer_id) REFERENCES customer(id)")
        ],
    )
    return SchemaSnapshot(
        database_name="dev",
        schemas=["public"],
        tables={"public.users": users, "public.customer": customer, "public.orders": orders},
        enums={"public.order_status": EnumMetadata(schema_name="public", name="order_status", values=["pending", "paid", "shipped", "refunded"])},
        sequences=[],
    )


class FakePreflight:
    def nullable_to_not_null(self, schema: str, table: str, column: str) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=1, sample_values=[None], evidence={"table": table, "column": column})

    def incompatible_type_to_numeric(self, schema: str, table: str, column: str) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=1, sample_values=["unknown"], evidence={"table": table, "column": column})

    def text_to_integer(self, schema: str, table: str, column: str) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=1, sample_values=["unknown"])

    def varchar_length_reduction(self, schema: str, table: str, column: str, max_length: int) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=1, sample_values=["too long"])

    def enum_mismatch(self, schema: str, table: str, column: str, allowed_values: list[str]) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=1, sample_values=["cancelled"], evidence={"allowed": allowed_values})

    def foreign_key_orphans(self, schema: str, table: str, columns: list[str], referenced_schema: str, referenced_table: str, referenced_columns: list[str]) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=1, sample_values=[999], evidence={"referenced_table": referenced_table})

    def unique_duplicates(self, schema: str, table: str, columns: list[str]) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=2, sample_values=[{"values": ["alex@example.com"], "count": 2}], evidence={"columns": columns})

    def probable_rename(self, schema: str, table: str, source_column: str, target_column: str) -> PreflightEvidence:
        return PreflightEvidence(affected_row_count=3, sample_values=["Acme Events"], evidence={"source": source_column, "target": target_column})


def test_normalize_type_for_enums_and_common_types():
    assert normalize_type({"data_type": "USER-DEFINED", "udt_name": "order_status"}) == "order_status"
    assert normalize_type({"data_type": "character varying", "udt_name": "varchar"}) == "varchar"
    assert normalize_type({"data_type": "numeric", "udt_name": "numeric"}) == "numeric"


def test_diff_detects_required_conflict_types():
    conflicts = detect_conflicts(snapshot_prod(), snapshot_dev(), FakePreflight())
    categories = {conflict.category for conflict in conflicts}
    assert {
        "nullable_to_not_null",
        "incompatible_type_change",
        "enum_value_mismatch",
        "new_foreign_key_orphans",
        "new_unique_constraint_duplicates",
        "probable_column_rename",
    } <= categories
    assert {"column_added", "column_removed", "enum_changed"} <= categories
    assert all(conflict.conflict_id for conflict in conflicts)
    assert sum(conflict.affected_row_count for conflict in conflicts) == 9


def test_diff_covers_generic_structural_objects():
    prod_common = TableMetadata(
        schema_name="inventory",
        name="common",
        columns={
            "id": column("common", "id", "integer", False),
            "email": column("common", "email", "varchar"),
            "username": column("common", "username", "varchar"),
        },
        constraints=[
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_pk", constraint_type="primary_key", columns=["id"], definition="PRIMARY KEY (id)"),
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_fk", constraint_type="foreign_key", columns=["id"], definition="FOREIGN KEY (id) REFERENCES old(id)", referenced_schema="inventory", referenced_table="old", referenced_columns=["id"]),
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_unique", constraint_type="unique", columns=["email"], definition="UNIQUE (email)"),
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_check", constraint_type="check", columns=["id"], definition="CHECK (id > 0)"),
        ],
        indexes=[
            IndexMetadata(schema_name="inventory", table_name="common", name="changed_idx", definition="CREATE INDEX changed_idx ON inventory.common (email)"),
            IndexMetadata(schema_name="inventory", table_name="common", name="removed_idx", definition="CREATE INDEX removed_idx ON inventory.common (id)"),
        ],
    )
    dev_common = TableMetadata(
        schema_name="inventory",
        name="common",
        columns=prod_common.columns,
        constraints=[
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_pk", constraint_type="primary_key", columns=["email"], definition="PRIMARY KEY (email)"),
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_fk", constraint_type="foreign_key", columns=["id"], definition="FOREIGN KEY (id) REFERENCES new(id)", referenced_schema="inventory", referenced_table="new", referenced_columns=["id"]),
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_unique", constraint_type="unique", columns=["username"], definition="UNIQUE (username)"),
            ConstraintMetadata(schema_name="inventory", table_name="common", name="common_check", constraint_type="check", columns=["id"], definition="CHECK (id >= 0)"),
        ],
        indexes=[
            IndexMetadata(schema_name="inventory", table_name="common", name="changed_idx", definition="CREATE INDEX changed_idx ON inventory.common (username)"),
            IndexMetadata(schema_name="inventory", table_name="common", name="added_idx", definition="CREATE INDEX added_idx ON inventory.common (id)"),
        ],
    )
    prod = SchemaSnapshot(
        database_name="prod",
        schemas=["inventory"],
        tables={
            "inventory.common": prod_common,
            "inventory.removed": TableMetadata(schema_name="inventory", name="removed"),
        },
        enums={
            "inventory.changed_enum": EnumMetadata(schema_name="inventory", name="changed_enum", values=["a", "b"]),
            "inventory.removed_enum": EnumMetadata(schema_name="inventory", name="removed_enum", values=["a"]),
        },
        sequences=[
            SequenceMetadata(schema_name="inventory", name="changed_seq", increment="1"),
            SequenceMetadata(schema_name="inventory", name="removed_seq", increment="1"),
        ],
    )
    dev = SchemaSnapshot(
        database_name="dev",
        schemas=["inventory"],
        tables={
            "inventory.common": dev_common,
            "inventory.added": TableMetadata(schema_name="inventory", name="added"),
        },
        enums={
            "inventory.changed_enum": EnumMetadata(schema_name="inventory", name="changed_enum", values=["a", "c"]),
            "inventory.added_enum": EnumMetadata(schema_name="inventory", name="added_enum", values=["a"]),
        },
        sequences=[
            SequenceMetadata(schema_name="inventory", name="changed_seq", increment="5"),
            SequenceMetadata(schema_name="inventory", name="added_seq", increment="1"),
        ],
    )

    categories = {item.category for item in detect_conflicts(prod, dev)}
    assert {
        "table_added", "table_removed", "primary_key_changed", "foreign_key_changed",
        "unique_constraint_changed", "check_constraint_changed", "index_added", "index_removed",
        "index_changed", "enum_added", "enum_removed", "enum_changed", "sequence_added",
        "sequence_removed", "sequence_changed",
    } <= categories
