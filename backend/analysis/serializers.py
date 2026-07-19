from __future__ import annotations

from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from .models import AnalysisRun, ApprovedAction, Conflict, ConnectionProfile, DryRunLog, RemediationPlan
from .services.localization import translate


class ConnectionProfileSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)
    passwordSet = serializers.SerializerMethodField()
    readOnly = serializers.SerializerMethodField()
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = ConnectionProfile
        fields = [
            "id", "name", "role", "host", "port", "database", "username", "password",
            "passwordSet", "sslmode", "selected_schemas", "statement_timeout", "readOnly",
            "last_test_status", "last_test_message", "last_tested_at", "is_demo", "created_at", "updated_at",
        ]
        read_only_fields = ["last_test_status", "last_test_message", "last_tested_at", "created_at", "updated_at"]

    def get_passwordSet(self, obj):
        return bool(obj.password)

    def get_readOnly(self, _obj):
        return True

    def get_is_demo(self, _obj):
        return False

    def validate_selected_schemas(self, value):
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            raise serializers.ValidationError(translate("validation.select_schema", self.context.get("locale", "ru")), code="select_schema")
        return list(dict.fromkeys(item.strip() for item in value))

    def validate_statement_timeout(self, value):
        if value < 100 or value > 120000:
            raise serializers.ValidationError(translate("validation.timeout", self.context.get("locale", "ru")), code="timeout")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({
                "password": [ErrorDetail(translate("validation.password", self.context.get("locale", "ru")), code="password")]
            })
        if self.instance is not None and "password" in attrs and not attrs["password"]:
            attrs.pop("password")
        return attrs


class ConflictSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conflict
        fields = [
            "id",
            "conflict_id",
            "schema_name",
            "table_name",
            "column_name",
            "constraint_name",
            "category",
            "object_type",
            "change_type",
            "severity",
            "breaking",
            "production_definition",
            "development_definition",
            "affected_row_count",
            "sample_values",
            "evidence",
            "preflight_status",
            "preflight_explanation",
            "sql_preview",
            "strategies",
            "created_at",
        ]


class RemediationPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = RemediationPlan
        fields = ["id", "provider", "model", "risk_level", "explanation", "content", "created_at"]


class ApprovedActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovedAction
        fields = [
            "id",
            "conflict_id",
            "action_type",
            "parameters",
            "rationale",
            "requires_approval",
            "approved",
            "status",
            "sql_preview",
            "created_at",
            "updated_at",
        ]


class DryRunLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DryRunLog
        fields = ["id", "sequence", "step", "status", "message", "rows_affected", "sql_preview", "created_at"]


class AnalysisRunSerializer(serializers.ModelSerializer):
    conflicts = ConflictSerializer(many=True, read_only=True)
    remediation_plan = RemediationPlanSerializer(read_only=True)
    actions = ApprovedActionSerializer(many=True, read_only=True)
    dry_run_logs = DryRunLogSerializer(many=True, read_only=True)

    class Meta:
        model = AnalysisRun
        fields = [
            "id",
            "status",
            "title",
            "mode",
            "locale",
            "production_profile",
            "development_profile",
            "source_metadata",
            "selected_schemas",
            "ignored_tables",
            "run_preflight",
            "ai_provider",
            "ai_model",
            "metrics",
            "report",
            "error",
            "dry_run_status",
            "created_at",
            "updated_at",
            "conflicts",
            "remediation_plan",
            "actions",
            "dry_run_logs",
        ]


class AnalysisSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisRun
        fields = ["id", "status", "title", "mode", "locale", "metrics", "dry_run_status", "created_at", "updated_at", "error"]
