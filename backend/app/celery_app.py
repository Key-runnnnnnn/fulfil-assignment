"""
Celery application configuration for async task processing.
Uses RabbitMQ as message broker and PostgreSQL as result backend.
"""
from celery import Celery
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery application
celery_app = Celery(
    "product_importer",
    broker=settings.get_celery_broker_url,
    backend=settings.get_celery_result_backend,
    include=['app.tasks.import_tasks', 'app.tasks.webhook_tasks']
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task execution settings
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,

    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_backend_transport_options={
        'master_name': 'mymaster',
    },

    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,

    # Task routing
    task_routes={
        'app.tasks.import_tasks.process_csv_import': {'queue': 'imports'},
        'app.tasks.webhook_tasks.send_webhook': {'queue': 'webhooks'},
    },

    # Task priority
    task_default_priority=5,

    # Acknowledgment settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,

    # Retry settings
    task_default_retry_delay=60,  # Retry after 60 seconds
    task_max_retries=3,

    # Beat schedule (for periodic tasks - if needed later)
    beat_schedule={},
)

# Configure logging
celery_app.conf.update(
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

logger.info(
    f"Celery app configured with broker: {settings.get_celery_broker_url}")
logger.info(f"Celery result backend: {settings.get_celery_result_backend}")
