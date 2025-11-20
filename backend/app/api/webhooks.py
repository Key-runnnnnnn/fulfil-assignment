from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Webhook
from app.schemas import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookTestResponse
)
from typing import List
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[WebhookResponse])
def list_webhooks(
    db: Session = Depends(get_db)
):
    webhooks = db.query(Webhook).order_by(Webhook.created_at.desc()).all()
    logger.info(f"Listed {len(webhooks)} webhooks")
    return webhooks


@router.get("/event-types")
def get_event_types():
    return {
        "event_types": [
            {
                "name": "import_complete",
                "description": "Triggered when a CSV import job completes (success or failure)"
            },
            {
                "name": "product_created",
                "description": "Triggered when a new product is created via API"
            },
            {
                "name": "product_updated",
                "description": "Triggered when an existing product is updated"
            },
            {
                "name": "product_deleted",
                "description": "Triggered when a product is deleted"
            }
        ]
    }


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not webhook:
        logger.warning(f"Webhook not found: ID {webhook_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )

    logger.info(f"Retrieved webhook: ID {webhook_id}, URL {webhook.url}")
    return webhook


@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    webhook: WebhookCreate,
    db: Session = Depends(get_db)
):
    webhook_data = {
        'url': str(webhook.url),
        'event_type': webhook.event_type,
        'is_enabled': webhook.is_enabled,
        'headers': json.dumps(webhook.headers) if webhook.headers else None
    }

    db_webhook = Webhook(**webhook_data)
    db.add(db_webhook)
    db.commit()
    db.refresh(db_webhook)

    logger.info(
        f"Created webhook: ID {db_webhook.id}, URL {db_webhook.url}, Event {db_webhook.event_type}")
    return db_webhook


@router.put("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: int,
    webhook: WebhookUpdate,
    db: Session = Depends(get_db)
):
    db_webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not db_webhook:
        logger.warning(f"Webhook not found for update: ID {webhook_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )

    update_data = webhook.model_dump(exclude_unset=True)

    if not update_data:
        logger.warning(
            f"No fields provided for webhook update: ID {webhook_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    if 'url' in update_data:
        update_data['url'] = str(update_data['url'])
    if 'headers' in update_data and update_data['headers'] is not None:
        update_data['headers'] = json.dumps(update_data['headers'])

    for field, value in update_data.items():
        setattr(db_webhook, field, value)

    db.commit()
    db.refresh(db_webhook)

    logger.info(f"Updated webhook: ID {webhook_id}")
    return db_webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    db_webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not db_webhook:
        logger.warning(f"Webhook not found for deletion: ID {webhook_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )

    url = db_webhook.url
    db.delete(db_webhook)
    db.commit()

    logger.info(f"Deleted webhook: ID {webhook_id}, URL {url}")
    return None


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not webhook:
        logger.warning(f"Webhook not found for testing: ID {webhook_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )

    if not webhook.is_enabled:  # type: ignore
        logger.warning(f"Attempted to test disabled webhook: ID {webhook_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot test a disabled webhook. Enable it first."
        )

    logger.info(f"Test webhook triggered: ID {webhook_id}, URL {webhook.url}")

    from app.tasks.webhook_tasks import test_webhook as test_webhook_task
    task = test_webhook_task.delay(webhook_id)  # type: ignore

    return WebhookTestResponse(
        message=f"Test webhook queued successfully. Check Celery logs for delivery status.",
        task_id=task.id,
        webhook_url=webhook.url
    )


@router.patch("/{webhook_id}/toggle", response_model=WebhookResponse)
def toggle_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found"
        )

    webhook.is_enabled = not webhook.is_enabled  # type: ignore
    db.commit()
    db.refresh(webhook)

    status_text = "enabled" if webhook.is_enabled else "disabled"
    logger.info(f"Toggled webhook {webhook_id} to {status_text}")

    return webhook
