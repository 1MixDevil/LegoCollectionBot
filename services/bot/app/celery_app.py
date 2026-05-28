"""Celery: тяжёлые коллажи вынесены из процесса бота."""

import os

from celery import Celery

_broker = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
_backend = os.getenv("CELERY_RESULT_BACKEND", _broker)

celery_app = Celery(
    "lego_bot",
    broker=_broker,
    backend=_backend,
    include=["app.tasks.collage_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("TZ", "Europe/Moscow"),
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="collage",
    task_routes={
        "collage.*": {"queue": "collage"},
    },
    task_soft_time_limit=int(os.getenv("COLLAGE_TASK_SOFT_LIMIT", "900")),
    task_time_limit=int(os.getenv("COLLAGE_TASK_HARD_LIMIT", "1200")),
    broker_connection_retry_on_startup=True,
)
