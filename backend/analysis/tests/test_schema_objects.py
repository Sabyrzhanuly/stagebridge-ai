from __future__ import annotations

from analysis.services.diff_engine import detect_conflicts
from analysis.services.types import RoutineMetadata, SchemaSnapshot, TriggerMetadata, ViewMetadata


def _snapshot(*, routines=None, views=None, triggers=None) -> SchemaSnapshot:
    return SchemaSnapshot(
        database_name="d", schemas=["public"], tables={}, enums={}, sequences=[],
        routines=routines or {}, views=views or {}, triggers=triggers or {},
    )


def test_detects_routine_view_trigger_changes():
    prod = _snapshot(
        routines={"public.f()": RoutineMetadata(schema_name="public", name="f", definition="CREATE FUNCTION f() body v1")},
        views={"public.v": ViewMetadata(schema_name="public", name="v", definition="SELECT 1")},
    )
    dev = _snapshot(
        routines={
            "public.f()": RoutineMetadata(schema_name="public", name="f", definition="CREATE FUNCTION f() body v2"),
            "public.g()": RoutineMetadata(schema_name="public", name="g", definition="CREATE FUNCTION g() body"),
        },
        views={"public.v": ViewMetadata(schema_name="public", name="v", definition="SELECT 2")},
        triggers={"public.t.trg": TriggerMetadata(schema_name="public", table_name="t", name="trg", definition="CREATE TRIGGER trg ...")},
    )
    categories = {conflict.category for conflict in detect_conflicts(prod, dev, preflight_enabled=False)}
    assert "routine_changed" in categories
    assert "routine_added" in categories
    assert "view_changed" in categories
    assert "trigger_added" in categories


def test_identical_objects_produce_no_conflicts():
    routine = {"public.f()": RoutineMetadata(schema_name="public", name="f", definition="CREATE FUNCTION f()  body")}
    # То же определение, но с иным форматированием — не должно считаться изменением.
    routine_spaced = {"public.f()": RoutineMetadata(schema_name="public", name="f", definition="CREATE   FUNCTION f() body")}
    conflicts = detect_conflicts(_snapshot(routines=routine), _snapshot(routines=routine_spaced), preflight_enabled=False)
    assert not any(c.object_type == "routine" for c in conflicts)
