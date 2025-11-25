#!/bin/bash
# Start script for Celery worker on Render

echo "Starting Celery Worker..."

# Create uploads directory if it doesn't exist
mkdir -p /tmp/uploads

# Start Celery worker
exec celery -A app.celery_app worker \
  --loglevel=info \
  --queues=imports,webhooks \
  --concurrency=2 \
  --max-tasks-per-child=1000
