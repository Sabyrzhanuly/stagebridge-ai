from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("connections/", views.connections, name="connections"),
    path("connections/test/", views.connections_test, name="connections-test"),
    path("connections/<int:connection_id>/", views.connection_detail, name="connection-detail"),
    path("connections/<int:connection_id>/test/", views.connection_test, name="connection-profile-test"),
    path("analysis/", views.analysis_list, name="analysis-list"),
    path("analysis/run/", views.analysis_run, name="analysis-run"),
    path("analysis/<int:analysis_id>/", views.analysis_detail, name="analysis-detail"),
    path("analysis/<int:analysis_id>/ai-plan/", views.analysis_ai_plan, name="analysis-ai-plan"),
    path("analysis/<int:analysis_id>/actions/", views.analysis_actions, name="analysis-actions"),
    path("analysis/<int:analysis_id>/dry-run/", views.analysis_dry_run, name="analysis-dry-run"),
    path("analysis/<int:analysis_id>/migrate/", views.analysis_migrate, name="analysis-migrate"),
    path("analysis/<int:analysis_id>/report/", views.analysis_report, name="analysis-report"),
]
