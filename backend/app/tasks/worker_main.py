"""Entrypoint: Celery worker слушает platform + org-{slug} очереди."""
from __future__ import annotations

import sys

from app.tasks.celery_app import celery
from app.tasks.queues import list_worker_queues


def main() -> None:
    queues = ",".join(list_worker_queues())
    argv = ["worker", "-l", "info", "-c", "4", "-Q", queues, *sys.argv[1:]]
    celery.worker_main(argv)


if __name__ == "__main__":
    main()
