from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.config import settings
from app.tasks.queues import PLATFORM_QUEUE

celery = Celery(
    "pgadmin",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.backup_tasks",
        "app.tasks.monitor_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.scenario_tasks",
        "app.tasks.structure_sync_tasks",
        "app.tasks.pg_client_tasks",
        "app.tasks.server_health_tasks",
    ],
)

celery.conf.task_default_queue = PLATFORM_QUEUE
celery.conf.task_queues = (Queue(PLATFORM_QUEUE),)
celery.conf.task_create_missing_queues = True

# ack-early: сообщение подтверждается при СТАРТЕ задачи, а не после её завершения.
# Так длинные клоны/бэкапы НЕ упираются в RabbitMQ consumer_timeout (каким бы он
# ни был) — таймаут перестаёт играть роль, решение не зависит от длительности.
# Цена — нет авто-переотправки при падении worker; но для сайд-эффектных задач
# (клон/бэкап) это и не нужно (слепой повтор плодит temp_db и путает), а зависшие
# run добивает orphan-reaper (Celery inspect). См. long-task-broker-timeout.
celery.conf.task_acks_late = False
celery.conf.task_reject_on_worker_lost = False
celery.conf.worker_prefetch_multiplier = 1

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "run-scheduled-structure-syncs": {
            "task": "app.tasks.structure_sync_tasks.run_scheduled_structure_syncs",
            "schedule": 60.0,
        },
        "reap-stale-structure-sync-runs": {
            "task": "app.tasks.structure_sync_tasks.reap_stale_structure_sync_runs",
            "schedule": 60.0,
        },
        "collect-metrics-every-60s": {
            "task": "app.tasks.monitor_tasks.collect_all_metrics",
            "schedule": 60.0,
        },
        "check-server-health-every-60s": {
            "task": "app.tasks.server_health_tasks.check_all_server_health",
            "schedule": 60.0,
        },
        "run-scheduled-backups": {
            "task": "app.tasks.backup_tasks.run_scheduled_backups",
            "schedule": 60.0,
        },
        "check-alert-rules": {
            "task": "app.tasks.notification_tasks.check_alert_rules",
            "schedule": 120.0,
        },
        "cleanup-old-backups-daily": {
            "task": "app.tasks.backup_tasks.cleanup_old_backups",
            "schedule": crontab(hour=3, minute=0),
        },
        "run-scheduled-scenarios": {
            "task": "app.tasks.scenario_tasks.run_scheduled_scenarios",
            "schedule": 60.0,
        },
        "reap-orphaned-scenario-runs": {
            "task": "app.tasks.scenario_tasks.reap_orphaned_scenario_runs",
            "schedule": 60.0,
        },
        "cleanup-scenario-dumps-daily": {
            "task": "app.tasks.scenario_tasks.cleanup_scenario_dumps",
            "schedule": crontab(hour=3, minute=30),
        },
    },
)
