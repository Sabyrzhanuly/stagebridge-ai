from __future__ import annotations

import json
import os
from typing import Any

from django.db import transaction

from analysis.models import AnalysisRun, ApprovedAction, RemediationPlan

from .actions import render_sql_preview, validate_action_payload
from .types import RemediationPlanModel
from .localization import LANGUAGE_NAMES, normalize_locale, translate, translate_list


class AIPlanError(RuntimeError):
    pass


def create_plan_for_analysis(analysis: AnalysisRun) -> RemediationPlan:
    conflicts = [conflict_to_payload(conflict) for conflict in analysis.conflicts.all()]
    locale = normalize_locale(analysis.locale)
    provider_name, model_name, plan = get_provider_plan(conflicts, locale)
    with transaction.atomic():
        RemediationPlan.objects.filter(analysis=analysis).delete()
        ApprovedAction.objects.filter(analysis=analysis).delete()
        remediation = RemediationPlan.objects.create(
            analysis=analysis,
            provider=provider_name,
            model=model_name,
            risk_level=plan.overall_risk_level,
            explanation=plan.short_explanation,
            content=plan.model_dump(),
        )
        for action_model in plan.ordered_recommended_actions:
            action = validate_action_payload(action_model.model_dump())
            ApprovedAction.objects.create(
                analysis=analysis,
                conflict_id=action.conflict_id,
                action_type=action.action_type,
                parameters=action.parameters,
                rationale=action.rationale,
                requires_approval=action.requires_human_approval,
                approved=not action.requires_human_approval,
                sql_preview=render_sql_preview(action.action_type, action.parameters),
            )
        analysis.ai_provider = provider_name
        analysis.ai_model = model_name
        analysis.save(update_fields=["ai_provider", "ai_model", "updated_at"])
    return remediation


def get_provider_plan(conflicts: list[dict[str, Any]], locale: str = "ru") -> tuple[str, str, RemediationPlanModel]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    model_name = os.getenv("OPENAI_MODEL", "")
    if not api_key:
        return "mock", model_name or "deterministic-mock", mock_plan(conflicts, locale)
    if not model_name:
        raise AIPlanError(translate("ai.model_required", locale))
    return "openai", model_name, openai_plan(conflicts, model_name, locale)


def openai_plan(conflicts: list[dict[str, Any]], model_name: str, locale: str = "ru") -> RemediationPlanModel:
    from openai import OpenAI

    client = OpenAI()
    schema = RemediationPlanModel.model_json_schema()
    response = client.responses.create(
        model=model_name,
        input=[
            {
                "role": "system",
                "content": (
                    translate("ai.system", locale, language=LANGUAGE_NAMES[normalize_locale(locale)])
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "allowed_action_types": [
                            "reject_refresh",
                            "backfill_null_with_default",
                            "normalize_numeric_values",
                            "map_enum_values",
                            "remove_or_remap_orphans",
                            "deduplicate_values",
                            "map_renamed_column",
                            "postpone_constraint",
                            "validate_constraint",
                        ],
                        "conflicts": conflicts,
                    },
                    default=str,
                ),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "stagebridge_remediation_plan",
                "schema": schema,
                "strict": True,
            }
        },
    )
    raw_text = getattr(response, "output_text", "")
    if not raw_text:
        raise AIPlanError(translate("ai.empty_response", locale))
    return RemediationPlanModel.model_validate_json(raw_text)


def mock_plan(conflicts: list[dict[str, Any]], locale: str = "ru") -> RemediationPlanModel:
    actions: list[dict[str, Any]] = []
    blocking = []
    for conflict in conflicts:
        category = conflict["category"]
        conflict_id = conflict["conflict_id"]
        schema = conflict.get("schema") or "public"
        table = conflict.get("table") or "target_table"
        column = conflict.get("column") or "target_column"
        if conflict["severity"] == "Blocking":
            blocking.append(conflict_id)
        if category == "nullable_to_not_null":
            actions.append(
                {
                    "action_type": "backfill_null_with_default",
                    "conflict_id": conflict_id,
                    "rationale": translate("ai.rationale.backfill_null_with_default", locale),
                    "parameters": {"schema": schema, "table": table, "column": column, "default_value": "000-000-0000"},
                    "requires_human_approval": True,
                }
            )
        elif category in {"incompatible_type_change", "text_to_integer", "type_change", "varchar_length_reduction"}:
            actions.append(
                {
                    "action_type": "normalize_numeric_values",
                    "conflict_id": conflict_id,
                    "rationale": translate("ai.rationale.normalize_numeric_values", locale),
                    "parameters": {"schema": schema, "table": table, "column": column, "reject_invalid": True},
                    "requires_human_approval": True,
                }
            )
        elif category == "enum_value_mismatch":
            actions.append(
                {
                    "action_type": "map_enum_values",
                    "conflict_id": conflict_id,
                    "rationale": translate("ai.rationale.map_enum_values", locale),
                    "parameters": {"schema": schema, "table": table, "column": column, "mapping": {}},
                    "requires_human_approval": True,
                }
            )
        elif category == "new_foreign_key_orphans":
            actions.append(
                {
                    "action_type": "remove_or_remap_orphans",
                    "conflict_id": conflict_id,
                    "rationale": translate("ai.rationale.remove_or_remap_orphans", locale),
                    "parameters": {"schema": schema, "table": table, "column": column, "mode": "reject"},
                    "requires_human_approval": True,
                }
            )
        elif category == "new_unique_constraint_duplicates":
            actions.append(
                {
                    "action_type": "deduplicate_values",
                    "conflict_id": conflict_id,
                    "rationale": translate("ai.rationale.deduplicate_values", locale),
                    "parameters": {"schema": schema, "table": table, "columns": [part for part in column.split(",") if part], "strategy": "keep_lowest_id"},
                    "requires_human_approval": True,
                }
            )
        elif category == "probable_column_rename":
            actions.append(
                {
                    "action_type": "map_renamed_column",
                    "conflict_id": conflict_id,
                    "rationale": translate("ai.rationale.map_renamed_column", locale),
                    "parameters": {"schema": schema, "table": table, "source_column": column.split("->", 1)[0], "target_column": column.split("->", 1)[-1]},
                    "requires_human_approval": True,
                }
            )
        elif conflict.get("breaking"):
            actions.append(
                {
                    "action_type": "reject_refresh",
                    "conflict_id": conflict_id,
                    "rationale": translate("ai.rationale.reject_refresh", locale),
                    "parameters": {"schema": schema, "table": table},
                    "requires_human_approval": True,
                }
            )

    actions.append(
        {
            "action_type": "validate_constraint",
            "conflict_id": "",
            "rationale": translate("ai.rationale.validate_constraint", locale),
            "parameters": {"scope": "dryrun"},
            "requires_human_approval": False,
        }
    )
    return RemediationPlanModel.model_validate(
        {
            "overall_risk_level": "Blocking" if blocking else "Warning" if conflicts else "Safe",
            "short_explanation": translate("ai.explanation", locale),
            "blocking_issues": blocking,
            "ordered_recommended_actions": actions,
            "alternative_strategies": translate_list("ai.alternatives", locale),
            "actions_requiring_human_approval": [action["action_type"] for action in actions if action["requires_human_approval"]],
            "validation_checks": translate_list("ai.checks", locale),
            "rollback_considerations": translate_list("ai.rollback", locale),
        }
    )


def conflict_to_payload(conflict) -> dict[str, Any]:
    return {
        "conflict_id": conflict.conflict_id,
        "schema": conflict.schema_name,
        "table": conflict.table_name,
        "column": conflict.column_name,
        "constraint": conflict.constraint_name,
        "category": conflict.category,
        "severity": conflict.severity,
        "breaking": conflict.breaking,
        "affected_row_count": conflict.affected_row_count,
        "sample_values": conflict.sample_values,
        "evidence": conflict.evidence,
        "possible_resolution_strategies": conflict.strategies,
    }
