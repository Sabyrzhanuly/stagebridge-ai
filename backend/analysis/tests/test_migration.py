from __future__ import annotations

import pytest

from analysis.models import AnalysisRun
from analysis.services.migration import MigrationExecutor, _ColumnPlan
from analysis.services.types import ColumnMetadata, ConstraintMetadata, SchemaSnapshot, TableMetadata


def _column(name: str, ntype: str, *, nullable: bool = True, max_length: int | None = None) -> ColumnMetadata:
    return ColumnMetadata(
        schema_name="public", table_name="t", name=name, ordinal_position=1,
        data_type=ntype, normalized_type=ntype, nullable=nullable, max_length=max_length,
    )


@pytest.mark.django_db
def test_transform_added_column_gets_default():
    ex = MigrationExecutor(AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={}))
    plan = _ColumnPlan(column=_column("required_tag", "text", nullable=False), source=None, kind="added")
    plan.default_value = ""
    assert ex._transform(plan, None) == ("", None)


@pytest.mark.django_db
def test_transform_backfills_null_for_not_null():
    ex = MigrationExecutor(AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={}))
    plan = _ColumnPlan(column=_column("nickname", "text", nullable=False), source="nickname", kind="direct")
    plan.default_value = "000"
    assert ex._transform(plan, None) == ("000", None)


@pytest.mark.django_db
def test_transform_rejects_invalid_numeric_and_integer():
    ex = MigrationExecutor(AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={}))
    numeric = _ColumnPlan(column=_column("credit", "numeric"), source="credit", kind="direct",
                          categories={"incompatible_type_change"})
    assert ex._transform(numeric, "not-a-number") == (None, "invalid_numeric")
    assert ex._transform(numeric, "120.50")[1] is None

    integer = _ColumnPlan(column=_column("age", "integer"), source="age", kind="direct",
                          categories={"text_to_integer"})
    assert ex._transform(integer, "unknown") == (None, "invalid_integer")
    assert ex._transform(integer, "42")[1] is None


@pytest.mark.django_db
def test_transform_truncates_varchar_over_limit():
    ex = MigrationExecutor(AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={}))
    plan = _ColumnPlan(column=_column("ref", "varchar", max_length=12), source="ref", kind="direct",
                       categories={"varchar_length_reduction"}, varchar_limit=12)
    value, reason = ex._transform(plan, "ABCDEFGHIJKLMNO")
    assert reason is None and value == "ABCDEFGHIJKL" and len(value) == 12


@pytest.mark.django_db
def test_transform_maps_or_rejects_removed_enum():
    ex = MigrationExecutor(AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={}))
    plan = _ColumnPlan(column=_column("state", "shipment_state"), source="state", kind="direct",
                       categories={"enum_value_mismatch"}, removed_enum={"cancelled"},
                       allowed_enum={"queued", "sent", "returned"}, enum_mapping={"cancelled": "returned"})
    assert ex._transform(plan, "cancelled") == ("returned", None)

    plan.enum_mapping = {}
    assert ex._transform(plan, "cancelled") == (None, "unsupported_enum_value")


@pytest.mark.django_db
def test_topo_sort_orders_parent_before_child():
    ex = MigrationExecutor(AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={}))
    parent = TableMetadata(schema_name="inventory", name="regions")
    child = TableMetadata(schema_name="inventory", name="accounts")
    child.constraints.append(ConstraintMetadata(
        schema_name="inventory", table_name="accounts", name="fk", constraint_type="foreign_key",
        columns=["region_id"], definition="FOREIGN KEY (region_id) REFERENCES regions(id)",
        referenced_schema="inventory", referenced_table="regions", referenced_columns=["id"],
    ))
    dev = SchemaSnapshot(
        database_name="d", schemas=["inventory"],
        tables={"inventory.regions": parent, "inventory.accounts": child}, enums={}, sequences=[],
    )
    order = ex._topo_sort(dev)
    assert order.index("inventory.regions") < order.index("inventory.accounts")


@pytest.mark.django_db
def test_migration_gate_requires_completed_analysis():
    analysis = AnalysisRun.objects.create(status=AnalysisRun.Status.RUNNING, metrics={}, locale="en")
    result = MigrationExecutor(analysis).run()
    analysis.refresh_from_db()
    assert not result.passed
    assert analysis.dry_run_status == AnalysisRun.DryRunStatus.FAILED
