from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from analysis.models import AnalysisRun, Conflict, ConnectionProfile


def profile_payload(**overrides):
    payload = {
        "name": "Live production",
        "role": "production",
        "host": "postgres",
        "port": 5432,
        "database": "stagebridge_live_prod",
        "username": "stagebridge",
        "password": "super-secret-value",
        "sslmode": "prefer",
        "selected_schemas": ["inventory"],
        "statement_timeout": 2500,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_connection_profile_crud_never_returns_password():
    client = APIClient()
    created = client.post("/api/connections/", profile_payload(), format="json")
    assert created.status_code == 201
    assert "password" not in created.data
    assert created.data["passwordSet"] is True

    listed = client.get("/api/connections/")
    saved = next(item for item in listed.data["connections"] if item.get("id") == created.data["id"])
    assert "password" not in saved
    assert any(item.get("is_demo") for item in listed.data["connections"])

    updated = client.patch(
        f"/api/connections/{created.data['id']}/",
        {"name": "Updated production", "selected_schemas": ["inventory", "audit"]},
        format="json",
    )
    assert updated.status_code == 200
    assert "password" not in updated.data
    assert ConnectionProfile.objects.get(id=created.data["id"]).password == "super-secret-value"


@pytest.mark.django_db
def test_live_analysis_cannot_run_demo_dryrun():
    analysis = AnalysisRun.objects.create(mode=AnalysisRun.Mode.LIVE, status=AnalysisRun.Status.COMPLETED)
    response = APIClient().post(f"/api/analysis/{analysis.id}/dry-run/", {"locale": "en"}, format="json")
    assert response.status_code == 409
    assert "demo data" in response.data["error"]


@pytest.mark.django_db
def test_markdown_and_json_reports_are_downloadable_without_passwords():
    profile = ConnectionProfile.objects.create(**profile_payload())
    analysis = AnalysisRun.objects.create(
        mode=AnalysisRun.Mode.LIVE,
        status=AnalysisRun.Status.COMPLETED,
        production_profile=profile,
        source_metadata={"production": {"name": profile.name, "host": profile.host, "database": profile.database}},
        selected_schemas=["inventory"],
        metrics={"schemaChangesDetected": 1, "breakingChanges": 1, "blockingConflicts": 1, "affectedRows": 2},
        locale="en",
    )
    Conflict.objects.create(
        analysis=analysis,
        conflict_id="nullable_to_not_null:inventory.accounts:nickname",
        schema_name="inventory",
        table_name="accounts",
        column_name="nickname",
        category="nullable_to_not_null",
        object_type="column",
        change_type="changed",
        severity="Blocking",
        breaking=True,
        production_definition={"nullable": True},
        development_definition={"nullable": False},
        affected_row_count=2,
        preflight_status="checked",
        preflight_explanation="NULL values cannot satisfy NOT NULL.",
        sql_preview='ALTER TABLE "inventory"."accounts" ALTER COLUMN "nickname" SET NOT NULL;',
    )
    client = APIClient()
    markdown = client.get(f"/api/analysis/{analysis.id}/report/?format=markdown&locale=en")
    assert markdown.status_code == 200
    assert markdown["Content-Type"].startswith("text/markdown")
    assert b"LIVE DATABASE ANALYSIS" in markdown.content
    assert b"super-secret-value" not in markdown.content

    json_report = client.get(f"/api/analysis/{analysis.id}/report/?format=json&locale=en")
    assert json_report.status_code == 200
    assert b'"passwords_included": false' in json_report.content
    assert b'"password"' not in json_report.content
