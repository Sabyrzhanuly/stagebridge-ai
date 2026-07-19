from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from analysis.models import AnalysisRun, Conflict
from analysis.services.ai_provider import mock_plan
from analysis.services.localization import normalize_locale, translate
from analysis.services.reporting import markdown_report


def test_locale_normalization_defaults_to_russian():
    assert normalize_locale("") == "ru"
    assert normalize_locale("kk-KZ") == "kk"
    assert normalize_locale("en-US,en;q=0.9") == "en"
    assert normalize_locale("de") == "ru"


def test_mock_plan_is_localized_for_all_supported_languages():
    conflict = {
        "category": "nullable_to_not_null", "conflict_id": "c1", "schema": "public",
        "table": "users", "column": "phone", "severity": "Blocking", "breaking": True,
    }
    assert "advisory" in mock_plan([conflict], "en").short_explanation
    assert "рекомендательный" in mock_plan([conflict], "ru").short_explanation
    assert "кеңес" in mock_plan([conflict], "kk").short_explanation


@pytest.mark.django_db
def test_connection_validation_uses_requested_locale():
    payload = {
        "name": "Missing password", "role": "production", "host": "postgres", "port": 5432,
        "database": "db", "username": "user", "sslmode": "prefer", "selected_schemas": ["public"],
        "statement_timeout": 5000, "locale": "kk",
    }
    response = APIClient().post("/api/connections/", payload, format="json")
    assert response.status_code == 400
    assert response.data["code"] == "validation_error"
    assert "Құпиясөз" in response.data["field_errors"]["password"][0]


@pytest.mark.django_db
def test_reports_render_in_russian_and_kazakh():
    analysis = AnalysisRun.objects.create(
        status=AnalysisRun.Status.COMPLETED,
        locale="ru",
        selected_schemas=["public"],
        source_metadata={},
        metrics={"schemaChangesDetected": 1, "breakingChanges": 1, "blockingConflicts": 1, "affectedRows": 2},
    )
    Conflict.objects.create(
        analysis=analysis, conflict_id="nullable:c1", schema_name="public", table_name="users", column_name="phone",
        category="nullable_to_not_null", severity="Blocking", breaking=True, preflight_status="checked",
        affected_row_count=2, production_definition={}, development_definition={}, evidence={}, strategies=[],
    )
    assert "Результаты" in markdown_report(analysis, "ru")
    assert "Нәтижелер" in markdown_report(analysis, "kk")
    assert translate("analysis.complete", "en") == "Analysis complete"
