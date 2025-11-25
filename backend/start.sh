#!/bin/bash
# Start script for FastAPI backend on Render

echo "Starting Product Importer API..."

# Create uploads directory if it doesn't exist
mkdir -p /tmp/uploads

# Run database migrations (if using Alembic)
# alembic upgrade head

# Start the FastAPI application
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
