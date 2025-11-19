"""
Webhook Tasks
Handles asynchronous webhook notifications for various events.
"""
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Webhook
from app.config import settings
import logging
import json
import httpx
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration from environment variables
WEBHOOK_TIMEOUT = settings.WEBHOOK_TIMEOUT_SECONDS
WEBHOOK_MAX_RETRIES = settings.WEBHOOK_MAX_RETRIES


@celery_app.task(bind=True, name='app.tasks.webhook_tasks.send_webhook', max_retries=WEBHOOK_MAX_RETRIES)
def send_webhook(self: Task, webhook_id: int, event_data: dict):
    """
    Send webhook notification asynchronously with retry logic.

    Args:
        webhook_id: ID of the webhook configuration
        event_data: Event payload to send

    This task:
    - Fetches webhook configuration from database
    - Sends HTTP POST request with custom headers
    - Retries on failure (up to 3 times with exponential backoff)
    - Logs success/failure

    Returns:
        dict: Status information about the webhook delivery
    """
    db = SessionLocal()

    try:
        logger.info(
            f"Sending webhook notification to webhook_id: {webhook_id}")

        # Fetch webhook configuration
        webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

        if not webhook:
            logger.error(f"Webhook {webhook_id} not found")
            return {
                'webhook_id': webhook_id,
                'status': 'error',
                'message': 'Webhook configuration not found'
            }

        if not webhook.is_enabled:
            logger.info(f"Webhook {webhook_id} is disabled, skipping")
            return {
                'webhook_id': webhook_id,
                'status': 'skipped',
                'message': 'Webhook is disabled'
            }

        # Prepare headers
        headers = {'Content-Type': 'application/json'}
        if webhook.headers:
            try:
                custom_headers = json.loads(webhook.headers)
                headers.update(custom_headers)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in webhook headers: {e}")

        # Prepare payload
        payload = {
            'event_type': webhook.event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': event_data
        }

        # Send HTTP POST request
        logger.info(f"Sending webhook to {webhook.url}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        with httpx.Client(timeout=WEBHOOK_TIMEOUT) as client:
            response = client.post(
                webhook.url,
                json=payload,
                headers=headers
            )

            # Check response status
            response.raise_for_status()

            logger.info(
                f"Webhook {webhook_id} sent successfully. Status: {response.status_code}")

            return {
                'webhook_id': webhook_id,
                'status': 'success',
                'status_code': response.status_code,
                'response_text': response.text[:500],  # First 500 chars
                'url': webhook.url
            }

    except httpx.HTTPStatusError as e:
        # HTTP error (4xx, 5xx)
        logger.error(
            f"Webhook {webhook_id} failed with HTTP error: {e.response.status_code}")

        # Retry on 5xx errors (server errors)
        if 500 <= e.response.status_code < 600:
            logger.info(
                f"Retrying webhook {webhook_id} (attempt {self.request.retries + 1}/{WEBHOOK_MAX_RETRIES})")
            # Exponential backoff
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

        return {
            'webhook_id': webhook_id,
            'status': 'error',
            'status_code': e.response.status_code,
            'message': f'HTTP error: {e.response.status_code}',
            'url': webhook.url if webhook else None
        }

    except httpx.RequestError as e:
        # Network error (connection, timeout, etc.)
        logger.error(
            f"Webhook {webhook_id} failed with network error: {str(e)}")

        # Retry on network errors
        logger.info(
            f"Retrying webhook {webhook_id} (attempt {self.request.retries + 1}/{WEBHOOK_MAX_RETRIES})")
        # Exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except Exception as e:
        logger.error(
            f"Webhook {webhook_id} failed with unexpected error: {str(e)}", exc_info=True)

        return {
            'webhook_id': webhook_id,
            'status': 'error',
            'message': f'Unexpected error: {str(e)}',
            'url': webhook.url if webhook else None
        }

    finally:
        db.close()


@celery_app.task(bind=True, name='app.tasks.webhook_tasks.trigger_webhooks_for_event')
def trigger_webhooks_for_event(self: Task, event_type: str, event_data: dict):
    """
    Trigger all enabled webhooks for a specific event type.

    Args:
        event_type: Type of event (import_complete, product_created, etc.)
        event_data: Event payload

    Finds all enabled webhooks for the event type and queues send_webhook tasks.

    Returns:
        dict: Summary of triggered webhooks
    """
    db = SessionLocal()

    try:
        logger.info(f"Triggering webhooks for event: {event_type}")

        # Find all enabled webhooks for this event type
        webhooks = db.query(Webhook).filter(
            Webhook.event_type == event_type,
            Webhook.is_enabled == True
        ).all()

        if not webhooks:
            logger.info(
                f"No enabled webhooks found for event type: {event_type}")
            return {
                'event_type': event_type,
                'triggered_count': 0,
                'message': 'No enabled webhooks found'
            }

        # Queue webhook tasks
        triggered_ids = []
        for webhook in webhooks:
            try:
                send_webhook.delay(webhook.id, event_data)
                triggered_ids.append(webhook.id)
                logger.info(f"Queued webhook {webhook.id} for {webhook.url}")
            except Exception as e:
                logger.error(f"Failed to queue webhook {webhook.id}: {str(e)}")

        logger.info(
            f"Triggered {len(triggered_ids)} webhooks for event: {event_type}")

        return {
            'event_type': event_type,
            'triggered_count': len(triggered_ids),
            'webhook_ids': triggered_ids,
            'message': f'Successfully queued {len(triggered_ids)} webhooks'
        }

    except Exception as e:
        logger.error(
            f"Failed to trigger webhooks for event {event_type}: {str(e)}", exc_info=True)

        return {
            'event_type': event_type,
            'triggered_count': 0,
            'error': str(e)
        }

    finally:
        db.close()


@celery_app.task(bind=True, name='app.tasks.webhook_tasks.test_webhook')
def test_webhook(self: Task, webhook_id: int):
    """
    Test a webhook by sending a test payload.

    Args:
        webhook_id: ID of the webhook to test

    Returns:
        dict: Test result
    """
    logger.info(f"Testing webhook {webhook_id}")

    # Send test payload
    test_payload = {
        'test': True,
        'message': 'This is a test webhook notification',
        'timestamp': datetime.utcnow().isoformat()
    }

    # Use the regular send_webhook task
    result = send_webhook(webhook_id, test_payload)

    return result
