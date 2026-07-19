from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from analysis.models import AnalysisRun, Conflict, ConnectionProfile

from .connections import (
    connect_to_profile,
    connect_to_target,
    list_demo_database_configs,
    profile_snapshot,
    test_database_connection,
)
from .diff_engine import detect_conflicts
from .preflight import PreflightRunner
from .schema_inspector import SchemaInspector
from .localization import normalize_locale, translate

DEMO_CATEGORIES = {
    "nullable_to_not_null",
    "incompatible_type_change",
    "enum_value_mismatch",
    "new_foreign_key_orphans",
    "new_unique_constraint_duplicates",
    "probable_column_rename",
}


def run_schema_analysis(
    *,
    mode: str = AnalysisRun.Mode.DEMO,
    production_profile: ConnectionProfile | None = None,
    development_profile: ConnectionProfile | None = None,
    selected_schemas: list[str] | None = None,
    ignored_tables: list[str] | None = None,
    run_preflight: bool = True,
    locale: str = "ru",
) -> AnalysisRun:
    locale = normalize_locale(locale)
    schemas = selected_schemas or ["public"]
    ignored = ignored_tables or []
    is_demo = mode == AnalysisRun.Mode.DEMO
    if not is_demo and (production_profile is None or development_profile is None):
        raise ValueError("Live analysis requires production and development connection profiles.")

    source_metadata = (
        {
            "production": next(item for item in list_demo_database_configs(locale) if item["target"] == "prod"),
            "development": next(item for item in list_demo_database_configs(locale) if item["target"] == "dev"),
        }
        if is_demo
        else {"production": profile_snapshot(production_profile), "development": profile_snapshot(development_profile)}
    )
    title = translate("analysis.demo_title", locale) if is_demo else f"{production_profile.name} vs {development_profile.name}"
    analysis = AnalysisRun.objects.create(
        status=AnalysisRun.Status.RUNNING,
        title=title,
        mode=mode,
        locale=locale,
        production_profile=production_profile,
        development_profile=development_profile,
        source_metadata=source_metadata,
        selected_schemas=schemas,
        ignored_tables=ignored,
        run_preflight=run_preflight,
    )
    try:
        if is_demo:
            prod_context = connect_to_target("prod", read_only=True)
            dev_context = connect_to_target("dev", read_only=True)
            prod_name = "stagebridge_prod"
            dev_name = "stagebridge_dev"
        else:
            prod_context = connect_to_profile(production_profile)
            dev_context = connect_to_profile(development_profile)
            prod_name = production_profile.database
            dev_name = development_profile.database

        with prod_context as prod_conn, dev_context as dev_conn:
            prod_snapshot = SchemaInspector(
                prod_conn,
                prod_name,
                selected_schemas=schemas,
                ignored_tables=ignored,
            ).inspect()
            dev_snapshot = SchemaInspector(
                dev_conn,
                dev_name,
                selected_schemas=schemas,
                ignored_tables=ignored,
            ).inspect()
            conflicts = detect_conflicts(
                prod_snapshot,
                dev_snapshot,
                PreflightRunner(prod_conn) if run_preflight else None,
                preflight_enabled=run_preflight,
            )
            if is_demo:
                conflicts = [conflict for conflict in conflicts if conflict.category in DEMO_CATEGORIES]

        with transaction.atomic():
            Conflict.objects.filter(analysis=analysis).delete()
            for conflict in conflicts:
                Conflict.objects.create(analysis=analysis, **conflict.model_dump())
            metrics = build_metrics(conflicts, approved_actions=0, dry_run_status=analysis.dry_run_status)
            analysis.metrics = metrics
            analysis.report = build_analysis_report(analysis, conflicts)
            analysis.status = AnalysisRun.Status.COMPLETED
            analysis.save(update_fields=["metrics", "report", "status", "updated_at"])
        return analysis
    except Exception as exc:
        analysis.status = AnalysisRun.Status.FAILED
        analysis.error = str(exc)
        analysis.report = {
            "status": translate("analysis.failed", locale),
            "mode": mode,
            "error": str(exc),
            "generatedAt": timezone.now().isoformat(),
        }
        analysis.save(update_fields=["status", "error", "report", "updated_at"])
        return analysis


def build_metrics(conflicts, *, approved_actions: int, dry_run_status: str, transferred_rows: int = 0, validation_failures: int = 0) -> dict[str, int | str]:
    return {
        "schemaChangesDetected": len(conflicts),
        "blockingConflicts": sum(1 for conflict in conflicts if conflict.severity == "Blocking"),
        "breakingChanges": sum(1 for conflict in conflicts if conflict.breaking),
        "tablesAdded": sum(1 for conflict in conflicts if conflict.object_type == "table" and conflict.change_type == "added"),
        "tablesRemoved": sum(1 for conflict in conflicts if conflict.object_type == "table" and conflict.change_type == "removed"),
        "columnsChanged": sum(1 for conflict in conflicts if conflict.object_type == "column"),
        "constraintsChanged": sum(1 for conflict in conflicts if conflict.object_type == "constraint"),
        "affectedRows": sum(int(conflict.affected_row_count or 0) for conflict in conflicts),
        "approvedActions": approved_actions,
        "dryRunStatus": dry_run_status,
        "transferredRows": transferred_rows,
        "validationFailures": validation_failures,
    }


def build_analysis_report(analysis: AnalysisRun, conflicts) -> dict[str, object]:
    return {
        "status": translate("analysis.complete", analysis.locale),
        "mode": analysis.mode,
        "label": translate("analysis.demo_label" if analysis.mode == AnalysisRun.Mode.DEMO else "analysis.live_label", analysis.locale),
        "generatedAt": timezone.now().isoformat(),
        "production": analysis.source_metadata.get("production", {}),
        "development": analysis.source_metadata.get("development", {}),
        "selectedSchemas": analysis.selected_schemas,
        "ignoredTables": analysis.ignored_tables,
        "preflightEnabled": analysis.run_preflight,
        "productionReadOnly": True,
        "summary": build_metrics(conflicts, approved_actions=0, dry_run_status=analysis.dry_run_status),
        "changes": [conflict.model_dump(mode="json") for conflict in conflicts],
        "limitation": (
            translate("analysis.demo_limitation", analysis.locale)
            if analysis.mode == AnalysisRun.Mode.DEMO
            else translate("analysis.live_limitation", analysis.locale)
        ),
    }


def connection_overview(locale: str = "ru") -> list[dict[str, object]]:
    return list_demo_database_configs(locale)


def test_connection(target: str, locale: str = "ru") -> dict[str, object]:
    if target not in {"prod", "dev", "stage", "dryrun"}:
        return {"ok": False, "target": target, "error": translate("errors.unsupported_demo_target", locale)}
    return test_database_connection(target, locale)  # type: ignore[arg-type]
