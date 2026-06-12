import os
import sys

# Ensure the src directory is on the path for absolute imports
_src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from celery import Celery
from celery.schedules import crontab
from config import settings

celery_app = Celery(
    "gsm_os",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
)

# Scheduled tasks
celery_app.conf.beat_schedule = {
    "search-biology-every-6-hours": {
        "task": "src.workers.tasks.search_biology",
        "schedule": crontab(hour="*/6", minute=0),
    },
    "search-ai-every-6-hours": {
        "task": "src.workers.tasks.search_ai",
        "schedule": crontab(hour="*/6", minute=30),
    },
    "search-materials-daily": {
        "task": "src.workers.tasks.search_materials",
        "schedule": crontab(hour=8, minute=0),
    },
    "search-medicine-daily": {
        "task": "src.workers.tasks.search_medicine",
        "schedule": crontab(hour=9, minute=0),
    },
    "run-replay-daily": {
        "task": "src.workers.tasks.run_replay",
        "schedule": crontab(hour=2, minute=0),
    },
    "detect-contradictions-daily": {
        "task": "src.workers.tasks.detect_contradictions",
        "schedule": crontab(hour=3, minute=0),
    },
    "detect-bottlenecks-daily": {
        "task": "src.workers.tasks.detect_bottlenecks",
        "schedule": crontab(hour=4, minute=0),
    },
    "generate-hypotheses-daily": {
        "task": "src.workers.tasks.generate_hypotheses",
        "schedule": crontab(hour=5, minute=0),
    },
    "dream-cycle-weekly": {
        "task": "src.workers.tasks.run_dream_cycle",
        "schedule": crontab(hour=1, minute=0, day_of_week="sunday"),
    },
}
