from __future__ import annotations

import json

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import AnalysisRun, ApprovedAction, ConnectionProfile
from .serializers import AnalysisRunSerializer, AnalysisSummarySerializer, ConnectionProfileSerializer
from .services.actions import ALLOWED_ACTION_TYPES, render_sql_preview
from .services.ai_provider import AIPlanError, create_plan_for_analysis
from .services.analysis_service import connection_overview, run_schema_analysis, test_connection
from .services.connections import external_hosts_enabled, test_adhoc_connection, test_profile_connection
from .services.dry_run import DryRunExecutor
from .services.migration import MigrationExecutor
from .services.reporting import export_payload, markdown_report
from .services.localization import request_locale, translate


@api_view(["GET"])
def health(_request):
    return Response({"status": "ok", "service": "stagebridge-backend"})


@api_view(["GET", "POST"])
def connections(request):
    locale = request_locale(request)
    if request.method == "POST":
        serializer = ConnectionProfileSerializer(data=request.data, context={"locale": locale})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(ConnectionProfileSerializer(profile).data, status=status.HTTP_201_CREATED)
    saved = ConnectionProfileSerializer(ConnectionProfile.objects.all(), many=True, context={"locale": locale}).data
    return Response(
        {
            "connections": [*connection_overview(locale), *saved],
            "externalHostsEnabled": external_hosts_enabled(),
            "credentialStorage": translate("connections.credential_storage", locale),
        }
    )


@api_view(["GET", "PATCH", "DELETE"])
def connection_detail(request, connection_id: int):
    locale = request_locale(request)
    profile = get_object_or_404(ConnectionProfile, id=connection_id)
    if request.method == "DELETE":
        profile.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    if request.method == "PATCH":
        serializer = ConnectionProfileSerializer(profile, data=request.data, partial=True, context={"locale": locale})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save(last_test_status="untested", last_test_message="")
        return Response(ConnectionProfileSerializer(profile).data)
    return Response(ConnectionProfileSerializer(profile).data)


@api_view(["POST"])
def connection_test(request, connection_id: int):
    profile = get_object_or_404(ConnectionProfile, id=connection_id)
    result = test_profile_connection(profile, request_locale(request))
    return Response(result, status=status.HTTP_200_OK if result.get("ok") else status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def connections_test(request):
    locale = request_locale(request)
    connection_id = request.data.get("connection_id")
    if connection_id is not None:
        profile = get_object_or_404(ConnectionProfile, id=connection_id)
        result = test_profile_connection(profile, locale)
        return Response(result, status=status.HTTP_200_OK if result.get("ok") else status.HTTP_400_BAD_REQUEST)
    if request.data.get("host"):
        result = test_adhoc_connection(request.data, locale)
        return Response(result, status=status.HTTP_200_OK if result.get("ok") else status.HTTP_400_BAD_REQUEST)
    target = request.data.get("target")
    if not isinstance(target, str):
        return Response({"ok": False, "error": translate("errors.target_required", locale), "code": "target_required"}, status=status.HTTP_400_BAD_REQUEST)
    result = test_connection(target, locale)
    return Response(result, status=status.HTTP_200_OK if result.get("ok") else status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def analysis_list(_request):
    analyses = AnalysisRun.objects.all()[:20]
    return Response({"analyses": AnalysisSummarySerializer(analyses, many=True).data})


@api_view(["POST"])
def analysis_run(request):
    locale = request_locale(request)
    mode = request.data.get("mode", AnalysisRun.Mode.DEMO)
    if mode not in {AnalysisRun.Mode.DEMO, AnalysisRun.Mode.LIVE}:
        return Response({"error": translate("errors.invalid_mode", locale), "code": "invalid_mode"}, status=status.HTTP_400_BAD_REQUEST)
    schemas = _string_list(request.data.get("schemas", ["public"]), "schemas", locale, required=True)
    ignored_tables = _string_list(request.data.get("ignored_tables", []), "ignored_tables", locale)
    if isinstance(schemas, Response):
        return schemas
    if isinstance(ignored_tables, Response):
        return ignored_tables
    production_profile = development_profile = None
    if mode == AnalysisRun.Mode.LIVE:
        production_profile = get_object_or_404(ConnectionProfile, id=request.data.get("production_profile_id"))
        development_profile = get_object_or_404(ConnectionProfile, id=request.data.get("development_profile_id"))
        if production_profile.role != ConnectionProfile.Role.PRODUCTION:
            return Response({"error": translate("errors.production_role", locale), "code": "production_role"}, status=status.HTTP_400_BAD_REQUEST)
        if development_profile.role != ConnectionProfile.Role.DEVELOPMENT:
            return Response({"error": translate("errors.development_role", locale), "code": "development_role"}, status=status.HTTP_400_BAD_REQUEST)
        if production_profile.id == development_profile.id:
            return Response({"error": translate("errors.profiles_different", locale), "code": "profiles_different"}, status=status.HTTP_400_BAD_REQUEST)
    analysis = run_schema_analysis(
        mode=mode,
        production_profile=production_profile,
        development_profile=development_profile,
        selected_schemas=schemas,
        ignored_tables=ignored_tables,
        run_preflight=bool(request.data.get("run_preflight", True)),
        locale=locale,
    )
    http_status = status.HTTP_201_CREATED if analysis.status == AnalysisRun.Status.COMPLETED else status.HTTP_500_INTERNAL_SERVER_ERROR
    return Response(AnalysisRunSerializer(analysis).data, status=http_status)


@api_view(["GET"])
def analysis_detail(_request, analysis_id: int):
    analysis = get_object_or_404(AnalysisRun, id=analysis_id)
    return Response(AnalysisRunSerializer(analysis).data)


@api_view(["POST"])
def analysis_ai_plan(request, analysis_id: int):
    analysis = get_object_or_404(AnalysisRun, id=analysis_id)
    locale = request_locale(request)
    if analysis.status != AnalysisRun.Status.COMPLETED:
        return Response({"error": translate("errors.analysis_incomplete", locale), "code": "analysis_incomplete"}, status=status.HTTP_409_CONFLICT)
    try:
        analysis.locale = locale
        analysis.save(update_fields=["locale", "updated_at"])
        create_plan_for_analysis(analysis)
    except AIPlanError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    analysis.refresh_from_db()
    return Response(AnalysisRunSerializer(analysis).data)


@api_view(["PATCH"])
def analysis_actions(request, analysis_id: int):
    analysis = get_object_or_404(AnalysisRun, id=analysis_id)
    locale = request_locale(request)
    if analysis.locale != locale:
        analysis.locale = locale
        analysis.save(update_fields=["locale", "updated_at"])
    updates = request.data.get("actions")
    if not isinstance(updates, list):
        return Response({"error": translate("errors.actions_list", locale), "code": "actions_list"}, status=status.HTTP_400_BAD_REQUEST)
    seen = []
    for update in updates:
        if not isinstance(update, dict):
            return Response({"error": translate("errors.action_object", locale), "code": "action_object"}, status=status.HTTP_400_BAD_REQUEST)
        action_id = update.get("id")
        action = get_object_or_404(ApprovedAction, id=action_id, analysis=analysis)
        action_type = update.get("action_type", action.action_type)
        if action_type not in ALLOWED_ACTION_TYPES:
            return Response({"error": translate("errors.unsupported_action", locale, action_type=action_type), "code": "unsupported_action"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        action.action_type = action_type
        if "parameters" in update:
            if not isinstance(update["parameters"], dict):
                return Response({"error": translate("errors.parameters_object", locale), "code": "parameters_object"}, status=status.HTTP_400_BAD_REQUEST)
            action.parameters = update["parameters"]
        if "approved" in update:
            action.approved = bool(update["approved"])
            action.status = "approved" if action.approved else "pending"
        action.sql_preview = render_sql_preview(action.action_type, action.parameters)
        action.save()
        seen.append(action.id)
    approved_actions = analysis.actions.filter(approved=True).count()
    metrics = dict(analysis.metrics or {})
    metrics["approvedActions"] = approved_actions
    analysis.metrics = metrics
    analysis.save(update_fields=["metrics", "updated_at"])
    analysis.refresh_from_db()
    return Response({"updated": seen, "analysis": AnalysisRunSerializer(analysis).data})


@api_view(["POST"])
def analysis_dry_run(request, analysis_id: int):
    analysis = get_object_or_404(AnalysisRun, id=analysis_id)
    locale = request_locale(request)
    if analysis.locale != locale:
        analysis.locale = locale
        analysis.save(update_fields=["locale", "updated_at"])
    if analysis.mode != AnalysisRun.Mode.DEMO:
        return Response(
            {"error": translate("errors.demo_dryrun_only", locale), "code": "demo_dryrun_only"},
            status=status.HTTP_409_CONFLICT,
        )
    result = DryRunExecutor(analysis).run()
    analysis.refresh_from_db()
    return Response(AnalysisRunSerializer(analysis).data, status=status.HTTP_200_OK if result.passed else status.HTTP_409_CONFLICT)


@api_view(["POST"])
def analysis_migrate(request, analysis_id: int):
    analysis = get_object_or_404(AnalysisRun, id=analysis_id)
    locale = request_locale(request)
    if analysis.locale != locale:
        analysis.locale = locale
        analysis.save(update_fields=["locale", "updated_at"])
    if analysis.status != AnalysisRun.Status.COMPLETED:
        return Response({"error": translate("errors.analysis_incomplete", locale), "code": "analysis_incomplete"}, status=status.HTTP_409_CONFLICT)
    if not analysis.actions.exists():
        return Response({"error": translate("migration.plan_required", locale), "code": "plan_required"}, status=status.HTTP_409_CONFLICT)

    target_profile = None
    staging_id = request.data.get("staging_profile_id")
    if staging_id is not None:
        target_profile = get_object_or_404(ConnectionProfile, id=staging_id)
        if target_profile.role != ConnectionProfile.Role.STAGING:
            return Response({"error": translate("errors.staging_role", locale), "code": "staging_role"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        if target_profile.id in {analysis.production_profile_id, analysis.development_profile_id}:
            return Response({"error": translate("errors.target_conflict", locale), "code": "target_conflict"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not request.data.get("confirm"):
            return Response({"error": translate("errors.confirm_required", locale), "code": "confirm_required"}, status=status.HTTP_400_BAD_REQUEST)

    result = MigrationExecutor(analysis, target_profile=target_profile).run()
    analysis.refresh_from_db()
    return Response(AnalysisRunSerializer(analysis).data, status=status.HTTP_200_OK if result.passed else status.HTTP_409_CONFLICT)


@api_view(["GET"])
def analysis_report(request, analysis_id: int):
    analysis = get_object_or_404(AnalysisRun, id=analysis_id)
    locale = request_locale(request)
    report_format = request.query_params.get("format", "")
    if report_format in {"markdown", "md"}:
        response = HttpResponse(markdown_report(analysis, locale), content_type="text/markdown; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="stagebridge-analysis-{analysis.id}.md"'
        return response
    payload = export_payload(analysis, locale)
    if report_format == "json":
        response = HttpResponse(json.dumps(payload, indent=2, default=str, ensure_ascii=False), content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="stagebridge-analysis-{analysis.id}.json"'
        return response
    return Response(payload)


def _string_list(value, field_name: str, locale: str = "ru", *, required: bool = False):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return Response({"error": translate("errors.string_list", locale, field=field_name), "code": "string_list"}, status=status.HTTP_400_BAD_REQUEST)
    result = list(dict.fromkeys(item.strip() for item in value if item.strip()))
    if required and not result:
        return Response({"error": translate("errors.non_empty_list", locale, field=field_name), "code": "non_empty_list"}, status=status.HTTP_400_BAD_REQUEST)
    return result
