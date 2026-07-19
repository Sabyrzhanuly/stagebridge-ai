from __future__ import annotations

from typing import Any

from analysis.serializers import AnalysisRunSerializer
from .localization import (
    generic_strategies,
    normalize_locale,
    translate,
    translate_category,
    translate_conflict_explanation,
    translate_status,
)


def export_payload(analysis, locale: str | None = None) -> dict[str, Any]:
    locale = normalize_locale(locale or analysis.locale)
    serialized = AnalysisRunSerializer(analysis).data
    serialized["locale"] = locale
    serialized["display"] = {
        "status": translate_status(serialized["status"], locale),
        "mode": translate("analysis.demo_label" if serialized["mode"] == "demo" else "analysis.live_label", locale),
    }
    for conflict in serialized.get("conflicts", []):
        conflict["category_label"] = translate_category(conflict["category"], locale)
        conflict["severity_label"] = translate_status(conflict["severity"], locale)
        conflict["preflight_status_label"] = translate_status(conflict.get("preflight_status", "not_run"), locale)
        conflict["preflight_explanation"] = translate_conflict_explanation(conflict["category"], locale)
        conflict["strategies"] = generic_strategies(locale)
        if (conflict.get("sql_preview") or "").strip().startswith("--"):
            conflict["sql_preview"] = translate("report.no_sql", locale)
    for action in serialized.get("actions", []):
        rationale = translate(f"ai.rationale.{action['action_type']}", locale)
        if not rationale.startswith("ai.rationale."):
            action["rationale"] = rationale
        if (action.get("sql_preview") or "").strip().startswith("--"):
            action["sql_preview"] = translate("report.no_sql", locale)
    plan = serialized.get("remediation_plan")
    if plan and plan.get("provider") == "mock":
        plan["explanation"] = translate("ai.explanation", locale)
        plan["content"]["short_explanation"] = translate("ai.explanation", locale)
        plan["content"]["alternative_strategies"] = list(generic_strategies(locale))
    return {
        "stagebridge_report_version": 1,
        "analysis": serialized,
        "safety": {
            "live_database_writes": False,
            "production_read_only": True,
            "passwords_included": False,
        },
    }


def markdown_report(analysis, locale: str | None = None) -> str:
    locale = normalize_locale(locale or analysis.locale)
    payload = export_payload(analysis, locale)
    data = payload["analysis"]
    metrics = data.get("metrics", {})
    source = data.get("source_metadata", {})
    lines = [
        f"# {translate('report.title', locale, id=data['id'])}",
        "",
        f"**{translate('report.mode', locale)}:** {translate('analysis.demo_label' if data['mode'] == 'demo' else 'analysis.live_label', locale)}",
        f"**{translate('report.status', locale)}:** {translate_status(data['status'], locale)}",
        f"**{translate('report.schemas', locale)}:** {', '.join(data.get('selected_schemas') or [])}",
        "",
        f"## {translate('report.sources', locale)}",
        "",
        f"- {translate('report.production', locale)}: {_source_label(source.get('production', {}))} ({translate('report.read_only', locale)})",
        f"- {translate('report.development', locale)}: {_source_label(source.get('development', {}))} ({translate('report.read_only', locale)})",
        "",
        f"## {translate('report.summary', locale)}",
        "",
        f"- {translate('report.schema_changes', locale)}: {metrics.get('schemaChangesDetected', 0)}",
        f"- {translate('report.breaking_changes', locale)}: {metrics.get('breakingChanges', 0)}",
        f"- {translate('report.blocking_conflicts', locale)}: {metrics.get('blockingConflicts', 0)}",
        f"- {translate('report.affected_rows', locale)}: {metrics.get('affectedRows', 0)}",
        "",
        f"## {translate('report.findings', locale)}",
        "",
    ]
    for conflict in data.get("conflicts", []):
        subject = conflict.get("column_name") or conflict.get("constraint_name") or conflict.get("table_name")
        lines.extend(
            [
                f"### {translate_category(conflict['category'], locale)}: {conflict.get('schema_name')}.{conflict.get('table_name')} / {subject}",
                "",
                f"- {translate('report.severity', locale)}: {translate_status(conflict['severity'], locale)}",
                f"- {translate('report.breaking', locale)}: {translate('report.yes' if conflict.get('breaking') else 'report.no', locale)}",
                f"- {translate('report.preflight', locale)}: {translate_status(conflict.get('preflight_status', 'not_run'), locale)}",
                f"- {translate('metrics.affected_rows', locale) if translate('metrics.affected_rows', locale) != 'metrics.affected_rows' else translate('report.affected_rows', locale)}: {conflict.get('affected_row_count', 0)}",
                f"- {translate('report.why', locale)}: {translate_conflict_explanation(conflict['category'], locale)}",
                f"- {translate('report.sample_values', locale)}: `{conflict.get('sample_values', [])}`",
                "",
                "```sql",
                conflict.get("sql_preview") or translate("report.no_sql", locale),
                "```",
                "",
            ]
        )
    if data.get("remediation_plan"):
        plan = data["remediation_plan"]
        explanation = translate("ai.explanation", locale) if plan.get("provider") == "mock" else plan.get("explanation", "")
        lines.extend([f"## {translate('report.remediation', locale)}", "", explanation, ""])
    lines.extend(
        [
            f"## {translate('report.safety', locale)}",
            "",
            translate("report.safety_text", locale),
            "",
        ]
    )
    return "\n".join(lines)


def _source_label(source: dict[str, Any]) -> str:
    name = source.get("name") or source.get("label") or "connection"
    database = source.get("database") or source.get("name") or "database"
    host = source.get("host") or "host"
    return f"{name} ({database} @ {host})"
