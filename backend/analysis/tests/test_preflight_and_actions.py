from __future__ import annotations

import pytest

from analysis.services.actions import render_sql_preview, validate_action_payload
from analysis.services.preflight import preview_table, render_preflight_preview, validate_identifier
from analysis.services.types import RemediationPlanModel


def test_identifier_safety_rejects_unsafe_names():
    assert validate_identifier("orders_2026") == "orders_2026"
    assert preview_table("orders") == '"public"."orders"'
    assert preview_table("orders;drop table users", "odd-schema") == '"odd-schema"."orders;drop table users"'
    with pytest.raises(ValueError):
        validate_identifier("bad\x00name")


def test_preflight_preview_is_controlled():
    preview = render_preflight_preview("nullable_to_not_null", "users", "phone")
    assert "phone" in preview
    assert "<numeric-regex>" not in preview


def test_unknown_action_type_is_rejected():
    with pytest.raises(ValueError):
        render_sql_preview("execute_ai_sql", {})
    with pytest.raises(ValueError):
        validate_action_payload({"action_type": "execute_ai_sql", "rationale": "bad", "parameters": {}})


def test_structured_ai_response_validation():
    plan = RemediationPlanModel.model_validate(
        {
            "overall_risk_level": "Blocking",
            "short_explanation": "Blocked by incompatible rows.",
            "blocking_issues": ["orders.price"],
            "ordered_recommended_actions": [
                {
                    "action_type": "normalize_numeric_values",
                    "conflict_id": "incompatible_type_change:orders:price",
                    "rationale": "Reject invalid numeric strings.",
                    "parameters": {"reject_invalid": True},
                    "requires_human_approval": True,
                }
            ],
            "alternative_strategies": ["Reject refresh"],
            "actions_requiring_human_approval": ["normalize_numeric_values"],
            "validation_checks": ["orders.price casts to numeric"],
            "rollback_considerations": ["Dry run can be reset"],
        }
    )
    assert plan.ordered_recommended_actions[0].action_type == "normalize_numeric_values"
