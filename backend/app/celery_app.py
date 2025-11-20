from celery import Celery
from app.config import settings
import logging

logger = logging.getLogger(__name__)

celery_app = Celery(
    "product_importer",
    broker=settings.get_celery_broker_url,
    backend=settings.get_celery_result_backend,
    include=['app.tasks.import_tasks', 'app.tasks.webhook_tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,

    result_expires=86400,
    result_backend_transport_options={
        'master_name': 'mymaster',
    },

    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,

    task_routes={
        'app.tasks.import_tasks.process_csv_import': {'queue': 'imports'},
        'app.tasks.webhook_tasks.send_webhook': {'queue': 'webhooks'},
        'app.tasks.webhook_tasks.test_webhook': {'queue': 'webhooks'},
        'app.tasks.webhook_tasks.trigger_webhooks_for_event': {'queue': 'webhooks'},
    },

    task_default_priority=5,

    task_acks_late=True,
    task_reject_on_worker_lost=True,

    task_default_retry_delay=60,
    task_max_retries=3,

    beat_schedule={},
)

celery_app.conf.update(
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

logger.info(
    f"Celery app configured with broker: {settings.get_celery_broker_url}")
logger.info(f"Celery result backend: {settings.get_celery_result_backend}")
