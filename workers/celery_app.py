from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "satellite_workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks.precompute", "workers.tasks.on_demand"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# Task routing
celery_app.conf.task_routes = {
    "workers.tasks.precompute.*": {"queue": "precompute"},
    "workers.tasks.on_demand.*": {"queue": "on_demand"},
}
