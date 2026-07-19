from __future__ import annotations

import pytest

from analysis.models import AnalysisRun, ApprovedAction
from analysis.services.actions import required_action_types_for_success
from analysis.services.dry_run import DryRunExecutor


@pytest.mark.django_db
def test_dry_run_failure_without_required_approvals():
    analysis = AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={}, locale="en")
    result = DryRunExecutor(analysis).run()
    analysis.refresh_from_db()
    assert not result.passed
    assert analysis.dry_run_status == AnalysisRun.DryRunStatus.FAILED
    assert "Missing approved actions" in analysis.dry_run_logs.first().message


@pytest.mark.django_db
def test_dry_run_success_path_with_isolated_executor_steps(monkeypatch):
    analysis = AnalysisRun.objects.create(status=AnalysisRun.Status.COMPLETED, metrics={})
    for action_type in required_action_types_for_success():
        ApprovedAction.objects.create(analysis=analysis, action_type=action_type, approved=True, parameters={}, rationale=action_type)

    class FakeConnectionContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_connect(*_args, **_kwargs):
        return FakeConnectionContext()

    executor = DryRunExecutor(analysis)
    monkeypatch.setattr("analysis.services.dry_run.connect_to_target", fake_connect)
    monkeypatch.setattr(executor, "_reset_dryrun", lambda _conn: executor._log("reset_dryrun_database", "passed", "ok"))
    monkeypatch.setattr(executor, "_apply_development_schema", lambda _conn: executor._log("apply_development_schema", "passed", "ok"))
    monkeypatch.setattr(executor, "_copy_production_rows", lambda _prod, _dry: {"users": 4, "customer": 3, "orders": 4})
    monkeypatch.setattr(executor, "_apply_transformations", lambda _conn, _actions: (8, 3))
    monkeypatch.setattr(executor, "_validate", lambda _conn: 0)

    result = executor.run()
    analysis.refresh_from_db()
    assert result.passed
    assert result.transferred_rows == 8
    assert analysis.dry_run_status == AnalysisRun.DryRunStatus.PASSED
    assert analysis.report["transferredRows"] == 8
