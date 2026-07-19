from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AnalysisRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("created", "Created"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="created", max_length=32)),
                ("title", models.CharField(default="Demo schema drift analysis", max_length=160)),
                ("ai_provider", models.CharField(blank=True, max_length=32)),
                ("ai_model", models.CharField(blank=True, max_length=120)),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("report", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("dry_run_status", models.CharField(choices=[("not_started", "Not started"), ("running", "Running"), ("passed", "Passed"), ("failed", "Failed")], default="not_started", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Conflict",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("conflict_id", models.CharField(max_length=80)),
                ("table_name", models.CharField(max_length=160)),
                ("column_name", models.CharField(blank=True, max_length=160)),
                ("constraint_name", models.CharField(blank=True, max_length=160)),
                ("category", models.CharField(max_length=80)),
                ("severity", models.CharField(max_length=32)),
                ("production_definition", models.JSONField(default=dict)),
                ("development_definition", models.JSONField(default=dict)),
                ("affected_row_count", models.IntegerField(default=0)),
                ("sample_values", models.JSONField(default=list)),
                ("evidence", models.JSONField(default=dict)),
                ("strategies", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conflicts", to="analysis.analysisrun")),
            ],
            options={"ordering": ["id"], "unique_together": {("analysis", "conflict_id")}},
        ),
        migrations.CreateModel(
            name="RemediationPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=32)),
                ("model", models.CharField(blank=True, max_length=120)),
                ("risk_level", models.CharField(max_length=32)),
                ("explanation", models.TextField()),
                ("content", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("analysis", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="remediation_plan", to="analysis.analysisrun")),
            ],
        ),
        migrations.CreateModel(
            name="ApprovedAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("conflict_id", models.CharField(blank=True, max_length=80)),
                ("action_type", models.CharField(max_length=80)),
                ("parameters", models.JSONField(default=dict)),
                ("rationale", models.TextField(blank=True)),
                ("requires_approval", models.BooleanField(default=True)),
                ("approved", models.BooleanField(default=False)),
                ("status", models.CharField(default="pending", max_length=32)),
                ("sql_preview", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="analysis.analysisrun")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="DryRunLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("step", models.CharField(max_length=120)),
                ("status", models.CharField(max_length=32)),
                ("message", models.TextField()),
                ("rows_affected", models.IntegerField(default=0)),
                ("sql_preview", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dry_run_logs", to="analysis.analysisrun")),
            ],
            options={"ordering": ["sequence", "id"]},
        ),
    ]

