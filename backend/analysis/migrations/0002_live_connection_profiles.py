import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("analysis", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="ConnectionProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("role", models.CharField(choices=[("production", "Production"), ("development", "Development"), ("staging", "Staging")], max_length=24)),
                ("host", models.CharField(max_length=255)),
                ("port", models.PositiveIntegerField(default=5432)),
                ("database", models.CharField(max_length=160)),
                ("username", models.CharField(max_length=160)),
                ("password", models.TextField()),
                ("sslmode", models.CharField(choices=[("disable", "Disable"), ("allow", "Allow"), ("prefer", "Prefer"), ("require", "Require"), ("verify-ca", "Verify CA"), ("verify-full", "Verify full")], default="prefer", max_length=16)),
                ("selected_schemas", models.JSONField(default=list)),
                ("statement_timeout", models.PositiveIntegerField(default=5000)),
                ("last_test_status", models.CharField(default="untested", max_length=24)),
                ("last_test_message", models.TextField(blank=True)),
                ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["role", "name"]},
        ),
        migrations.AddField(model_name="analysisrun", name="mode", field=models.CharField(choices=[("demo", "Demo data"), ("live", "Live database analysis")], default="demo", max_length=16)),
        migrations.AddField(model_name="analysisrun", name="source_metadata", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="analysisrun", name="selected_schemas", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="analysisrun", name="ignored_tables", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="analysisrun", name="run_preflight", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="analysisrun", name="production_profile", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="production_analyses", to="analysis.connectionprofile")),
        migrations.AddField(model_name="analysisrun", name="development_profile", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="development_analyses", to="analysis.connectionprofile")),
        migrations.AlterField(model_name="conflict", name="conflict_id", field=models.CharField(max_length=255)),
        migrations.AlterField(model_name="approvedaction", name="conflict_id", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="conflict", name="schema_name", field=models.CharField(default="public", max_length=160)),
        migrations.AddField(model_name="conflict", name="object_type", field=models.CharField(default="column", max_length=32)),
        migrations.AddField(model_name="conflict", name="change_type", field=models.CharField(default="changed", max_length=32)),
        migrations.AddField(model_name="conflict", name="breaking", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="conflict", name="preflight_status", field=models.CharField(default="not_run", max_length=32)),
        migrations.AddField(model_name="conflict", name="preflight_explanation", field=models.TextField(blank=True)),
        migrations.AddField(model_name="conflict", name="sql_preview", field=models.TextField(blank=True)),
    ]
