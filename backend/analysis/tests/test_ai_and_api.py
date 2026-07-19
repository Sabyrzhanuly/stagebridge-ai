from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from analysis.models import AnalysisRun, ApprovedAction, Conflict
from analysis.services.ai_provider import mock_plan


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.data["status"] == "ok"


def test_mock_plan_uses_allowlisted_actions():
    plan = mock_plan(
        [
            {
                "conflict_id": "nullable_to_not_null:users:phone",
                "category": "nullable_to_not_null",
                "severity": "Blocking",
            }
        ]
    )
    assert plan.overall_risk_level == "Blocking"
    assert plan.ordered_recommended_actions[0].action_type == "backfill_null_with_default"


@pytest.mark.django_db
def test_ai_plan_endpoint_persists_mock_actions(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    analysis = AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED)
    Conflict.objects.create(
        analysis=analysis,
        conflict_id="nullable_to_not_null:users:phone",
        table_name="users",
        column_name="phone",
        category="nullable_to_not_null",
        severity="Blocking",
        production_definition={},
        development_definition={},
        affected_row_count=1,
        sample_values=[None],
        evidence={},
        strategies=[],
    )
    client = APIClient()
    response = client.post(f"/api/analysis/{analysis.id}/ai-plan/")
    assert response.status_code == 200
    assert response.data["remediation_plan"]["provider"] == "mock"
    assert response.data["actions"][0]["action_type"] == "backfill_null_with_default"


@pytest.mark.django_db
def test_actions_endpoint_rejects_unsupported_action_type():
    analysis = AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED)
    action = ApprovedAction.objects.create(analysis=analysis, action_type="validate_constraint", rationale="validate")
    client = APIClient()
    response = client.patch(
        f"/api/analysis/{analysis.id}/actions/",
        {"actions": [{"id": action.id, "action_type": "execute_ai_sql", "approved": True}]},
        format="json",
    )
    assert response.status_code == 422

