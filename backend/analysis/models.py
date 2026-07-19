from __future__ import annotations

from django.db import models


class ConnectionProfile(models.Model):
    class Role(models.TextChoices):
        PRODUCTION = "production", "Production"
        DEVELOPMENT = "development", "Development"
        STAGING = "staging", "Staging"

    class SSLMode(models.TextChoices):
        DISABLE = "disable", "Disable"
        ALLOW = "allow", "Allow"
        PREFER = "prefer", "Prefer"
        REQUIRE = "require", "Require"
        VERIFY_CA = "verify-ca", "Verify CA"
        VERIFY_FULL = "verify-full", "Verify full"

    name = models.CharField(max_length=120, unique=True)
    role = models.CharField(max_length=24, choices=Role.choices)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=5432)
    database = models.CharField(max_length=160)
    username = models.CharField(max_length=160)
    password = models.TextField()
    sslmode = models.CharField(max_length=16, choices=SSLMode.choices, default=SSLMode.PREFER)
    selected_schemas = models.JSONField(default=list)
    statement_timeout = models.PositiveIntegerField(default=5000)
    last_test_status = models.CharField(max_length=24, default="untested")
    last_test_message = models.TextField(blank=True)
    last_tested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role", "name"]


class AnalysisRun(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class DryRunStatus(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        RUNNING = "running", "Running"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    class Mode(models.TextChoices):
        DEMO = "demo", "Demo data"
        LIVE = "live", "Live database analysis"

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED)
    title = models.CharField(max_length=160, default="Demo schema drift analysis")
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.DEMO)
    locale = models.CharField(max_length=8, default="ru")
    production_profile = models.ForeignKey(
        ConnectionProfile,
        related_name="production_analyses",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    development_profile = models.ForeignKey(
        ConnectionProfile,
        related_name="development_analyses",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    source_metadata = models.JSONField(default=dict, blank=True)
    selected_schemas = models.JSONField(default=list, blank=True)
    ignored_tables = models.JSONField(default=list, blank=True)
    run_preflight = models.BooleanField(default=True)
    ai_provider = models.CharField(max_length=32, blank=True)
    ai_model = models.CharField(max_length=120, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    report = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    dry_run_status = models.CharField(max_length=32, choices=DryRunStatus.choices, default=DryRunStatus.NOT_STARTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Conflict(models.Model):
    analysis = models.ForeignKey(AnalysisRun, related_name="conflicts", on_delete=models.CASCADE)
    conflict_id = models.CharField(max_length=255)
    schema_name = models.CharField(max_length=160, default="public")
    table_name = models.CharField(max_length=160)
    column_name = models.CharField(max_length=160, blank=True)
    constraint_name = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=80)
    object_type = models.CharField(max_length=32, default="column")
    change_type = models.CharField(max_length=32, default="changed")
    severity = models.CharField(max_length=32)
    breaking = models.BooleanField(default=False)
    production_definition = models.JSONField(default=dict)
    development_definition = models.JSONField(default=dict)
    affected_row_count = models.IntegerField(default=0)
    sample_values = models.JSONField(default=list)
    evidence = models.JSONField(default=dict)
    preflight_status = models.CharField(max_length=32, default="not_run")
    preflight_explanation = models.TextField(blank=True)
    sql_preview = models.TextField(blank=True)
    strategies = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("analysis", "conflict_id")]
        ordering = ["id"]


class RemediationPlan(models.Model):
    analysis = models.OneToOneField(AnalysisRun, related_name="remediation_plan", on_delete=models.CASCADE)
    provider = models.CharField(max_length=32)
    model = models.CharField(max_length=120, blank=True)
    risk_level = models.CharField(max_length=32)
    explanation = models.TextField()
    content = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class ApprovedAction(models.Model):
    analysis = models.ForeignKey(AnalysisRun, related_name="actions", on_delete=models.CASCADE)
    conflict_id = models.CharField(max_length=255, blank=True)
    action_type = models.CharField(max_length=80)
    parameters = models.JSONField(default=dict)
    rationale = models.TextField(blank=True)
    requires_approval = models.BooleanField(default=True)
    approved = models.BooleanField(default=False)
    status = models.CharField(max_length=32, default="pending")
    sql_preview = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]


class DryRunLog(models.Model):
    analysis = models.ForeignKey(AnalysisRun, related_name="dry_run_logs", on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField()
    step = models.CharField(max_length=120)
    status = models.CharField(max_length=32)
    message = models.TextField()
    rows_affected = models.IntegerField(default=0)
    sql_preview = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence", "id"]
