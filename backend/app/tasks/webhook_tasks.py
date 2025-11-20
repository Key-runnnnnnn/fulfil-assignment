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

WEBHOOK_TIMEOUT = settings.WEBHOOK_TIMEOUT_SECONDS
WEBHOOK_MAX_RETRIES = settings.WEBHOOK_MAX_RETRIES


@celery_app.task(bind=True, name='app.tasks.webhook_tasks.send_webhook', max_retries=WEBHOOK_MAX_RETRIES)
def send_webhook(self: Task, webhook_id: int, event_data: dict):
    db = SessionLocal()

    try:
        logger.info(
            f"Sending webhook notification to webhook_id: {webhook_id}")

        webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

        if not webhook:
            logger.error(f"Webhook {webhook_id} not found")
            return {
                'webhook_id': webhook_id,
                'status': 'error',
                'message': 'Webhook configuration not found'
            }

        if not webhook.is_enabled:  # type: ignore
            logger.info(f"Webhook {webhook_id} is disabled, skipping")
            return {
                'webhook_id': webhook_id,
                'status': 'skipped',
                'message': 'Webhook is disabled'
            }

        headers = {'Content-Type': 'application/json'}
        if webhook.headers:  # type: ignore
            try:
                custom_headers = json.loads(webhook.headers)  # type: ignore
                headers.update(custom_headers)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in webhook headers: {e}")

        payload = {
            'event_type': webhook.event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': event_data
        }

        logger.info(f"Sending webhook to {webhook.url}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

        with httpx.Client(timeout=WEBHOOK_TIMEOUT) as client:
            response = client.post(
                webhook.url,  # type: ignore
                json=payload,
                headers=headers
            )

            response.raise_for_status()

            logger.info(
                f"Webhook {webhook_id} sent successfully. Status: {response.status_code}")

            return {
                'webhook_id': webhook_id,
                'status': 'success',
                'status_code': response.status_code,
                'response_text': response.text[:500],
                'url': webhook.url
            }

    except httpx.HTTPStatusError as e:
        logger.error(
            f"Webhook {webhook_id} failed with HTTP error: {e.response.status_code}")

        if 500 <= e.response.status_code < 600:
            logger.info(
                f"Retrying webhook {webhook_id} (attempt {self.request.retries + 1}/{WEBHOOK_MAX_RETRIES})")
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

        return {
            'webhook_id': webhook_id,
            'status': 'error',
            'status_code': e.response.status_code,
            'message': f'HTTP error: {e.response.status_code}',
            'url': webhook.url if webhook else None
        }

    except httpx.RequestError as e:
        logger.error(
            f"Webhook {webhook_id} failed with network error: {str(e)}")

        logger.info(
            f"Retrying webhook {webhook_id} (attempt {self.request.retries + 1}/{WEBHOOK_MAX_RETRIES})")
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
    db = SessionLocal()

    try:
        logger.info(f"Triggering webhooks for event: {event_type}")

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

        triggered_ids = []
        for webhook in webhooks:
            try:
                send_webhook.delay(webhook.id, event_data)  # type: ignore
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
    logger.info(f"Testing webhook {webhook_id}")

    test_payload = {
        'test': True,
        'message': 'This is a test webhook notification',
        'timestamp': datetime.utcnow().isoformat()
    }

    result = send_webhook(self, webhook_id, test_payload)

    return result
