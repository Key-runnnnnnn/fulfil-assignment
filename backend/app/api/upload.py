"""
CSV File Upload API
Handles product CSV file uploads and initiates async import jobs.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import uuid
import csv
import io
import os
import asyncio
import json
from datetime import datetime
from typing import Optional

from app.database import get_db, SessionLocal
from app.models import ImportJob, Product
from app.schemas import UploadResponse, ImportJobStatus
from app.tasks.import_tasks import process_csv_import
from app.config import settings
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration from environment variables
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes
ALLOWED_EXTENSIONS = ['.csv']
UPLOAD_DIR = settings.UPLOAD_DIR

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)


def validate_csv_file(file: UploadFile) -> None:
    """
    Validate uploaded file is a CSV with proper format.

    Args:
        file: Uploaded file object

    Raises:
        HTTPException: If file validation fails
    """
    # Check file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed"
        )

    # Check content type
    if file.content_type not in ['text/csv', 'application/vnd.ms-excel', 'application/csv']:
        raise HTTPException(
            status_code=400,
            detail="Invalid content type. Must be a CSV file"
        )


def count_csv_rows(content: bytes) -> int:
    """
    Count the number of data rows in CSV file (excluding header).

    Args:
        content: CSV file content as bytes

    Returns:
        Number of data rows

    Raises:
        HTTPException: If CSV is invalid
    """
    try:
        text_content = content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(text_content))

        # Read header
        header = next(csv_reader, None)
        if not header:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # Validate required columns (price is optional)
        required_columns = ['sku', 'name', 'description']
        optional_columns = ['price']
        header_lower = [col.lower().strip() for col in header]

        for col in required_columns:
            if col not in header_lower:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column: {col}. Required columns: {', '.join(required_columns)}. Optional: {', '.join(optional_columns)}"
                )

        # Count data rows
        row_count = sum(1 for row in csv_reader if any(
            field.strip() for field in row))

        return row_count

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid CSV encoding. File must be UTF-8 encoded"
        )
    except csv.Error as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CSV format: {str(e)}"
        )


@router.post("/csv", response_model=UploadResponse, status_code=202)
async def upload_csv(
    file: UploadFile = File(...,
                            description="CSV file containing product data"),
    db: Session = Depends(get_db)
):
    """
    Upload a CSV file for product import.

    - **file**: CSV file with columns: sku, name, description, price
    - **max_size**: 100 MB
    - **encoding**: UTF-8

    Returns job_id and task_id for tracking import progress.
    The import process runs asynchronously via Celery.

    **CSV Format Example:**
    ```
    sku,name,description,price
    PROD001,Product One,Description here,19.99
    PROD002,Product Two,Another description,29.99
    ```
    """
    # Validate file
    validate_csv_file(file)

    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    # Count rows in CSV
    total_rows = count_csv_rows(content)

    if total_rows == 0:
        raise HTTPException(
            status_code=400,
            detail="CSV file contains no data rows"
        )

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Save file to disk
    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Create import job record
    import_job = ImportJob(
        id=job_id,
        filename=file.filename,
        total_rows=total_rows,
        processed_rows=0,
        success_count=0,
        error_count=0,
        status='pending',
        started_at=datetime.utcnow()
    )

    db.add(import_job)
    db.commit()
    db.refresh(import_job)

    # Try to queue Celery task for async processing
    # If RabbitMQ is not available, process synchronously
    try:
        task = process_csv_import.delay(job_id, file_path)
        task_id = task.id
    except Exception as e:
        logger.warning(
            f"Celery not available, processing synchronously: {str(e)}")
        # Process synchronously if Celery is not available
        try:
            # Import the task function and run it directly
            from app.tasks.import_tasks import process_csv_import_sync
            process_csv_import_sync(job_id, file_path)
            task_id = "sync-execution"
        except Exception as sync_error:
            logger.error(f"Synchronous processing failed: {str(sync_error)}")
            # Update job status to failed
            import_job.status = 'failed'
            import_job.error_message = str(sync_error)
            db.commit()
            raise HTTPException(
                status_code=500, detail=f"Processing failed: {str(sync_error)}")

    return UploadResponse(
        job_id=job_id,
        task_id=task_id,
        filename=file.filename,
        message=f"File uploaded successfully. Processing {total_rows} rows. Use job_id to track progress."
    )


@router.get("/status/{job_id}", response_model=ImportJobStatus)
async def get_import_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the status of an import job.

    - **job_id**: The unique import job ID returned from upload

    Returns current progress, row counts, and status.
    Use this endpoint to poll for updates or implement SSE for real-time tracking.
    """
    import_job = db.query(ImportJob).filter(ImportJob.id == job_id).first()

    if not import_job:
        raise HTTPException(status_code=404, detail="Import job not found")

    # Calculate progress percentage
    progress = 0.0
    if import_job.total_rows > 0:
        progress = (import_job.processed_rows / import_job.total_rows) * 100

    return ImportJobStatus(
        job_id=import_job.id,
        filename=import_job.filename,
        total_rows=import_job.total_rows,
        processed_rows=import_job.processed_rows,
        success_count=import_job.success_count,
        error_count=import_job.error_count,
        status=import_job.status,
        error_message=import_job.error_message,
        started_at=import_job.started_at,
        completed_at=import_job.completed_at,
        progress_percentage=round(progress, 2)
    )


@router.get("/jobs", response_model=list[ImportJobStatus])
async def list_import_jobs(
    limit: int = 10,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List recent import jobs.

    - **limit**: Maximum number of jobs to return (default: 10, max: 100)
    - **status_filter**: Filter by status (pending, processing, completed, failed)

    Returns list of import jobs ordered by most recent first.
    """
    if limit > 100:
        limit = 100

    query = db.query(ImportJob)

    # Apply status filter if provided
    if status_filter:
        allowed_statuses = ['pending', 'processing', 'completed', 'failed']
        if status_filter not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}"
            )
        query = query.filter(ImportJob.status == status_filter)

    # Order by most recent and limit
    jobs = query.order_by(ImportJob.started_at.desc()).limit(limit).all()

    # Convert to response schema
    result = []
    for job in jobs:
        progress = 0.0
        if job.total_rows > 0:
            progress = (job.processed_rows / job.total_rows) * 100

        result.append(ImportJobStatus(
            job_id=job.id,
            filename=job.filename,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            success_count=job.success_count,
            error_count=job.error_count,
            status=job.status,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
            progress_percentage=round(progress, 2)
        ))

    return result


@router.get("/progress/{job_id}")
async def stream_import_progress(job_id: str):
    """
    Stream real-time import progress using Server-Sent Events (SSE).

    - **job_id**: The unique import job ID

    Returns a stream of progress updates in SSE format.
    Client should connect with EventSource API.

    **Example (JavaScript):**
    ```javascript
    const eventSource = new EventSource('/api/v1/upload/progress/{job_id}');

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Progress:', data.progress_percentage + '%');

        if (data.status === 'completed' || data.status === 'failed') {
            eventSource.close();
        }
    };

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();
    };
    ```

    **SSE Data Format:**
    ```json
    {
        "job_id": "uuid",
        "status": "processing",
        "progress_percentage": 45.5,
        "processed_rows": 227500,
        "total_rows": 500000,
        "success_count": 227000,
        "error_count": 500
    }
    ```
    """
    async def event_generator():
        """Generate SSE events for import progress"""
        db = SessionLocal()

        try:
            # Check if job exists
            import_job = db.query(ImportJob).filter(
                ImportJob.id == job_id).first()

            if not import_job:
                # Send error event
                yield f"event: error\ndata: {{\"error\": \"Import job not found\"}}\n\n"
                return

            previous_status = None
            previous_processed = -1

            # Stream updates until job completes or fails
            while True:
                # Refresh job data
                db.refresh(import_job)

                # Calculate progress
                progress = 0.0
                if import_job.total_rows > 0:
                    progress = (import_job.processed_rows /
                                import_job.total_rows) * 100

                # Only send update if progress changed
                if (import_job.processed_rows != previous_processed or
                        import_job.status != previous_status):

                    # Prepare progress data
                    progress_data = {
                        "job_id": import_job.id,
                        "status": import_job.status,
                        "progress_percentage": round(progress, 2),
                        "processed_rows": import_job.processed_rows,
                        "total_rows": import_job.total_rows,
                        "success_count": import_job.success_count,
                        "error_count": import_job.error_count,
                        "timestamp": datetime.utcnow().isoformat()
                    }

                    # Add completion time if available
                    if import_job.completed_at:
                        progress_data["completed_at"] = import_job.completed_at.isoformat(
                        )

                    # Add error message if failed
                    if import_job.status == 'failed' and import_job.error_message:
                        progress_data["error_message"] = import_job.error_message

                    # Send SSE event
                    yield f"data: {json.dumps(progress_data)}\n\n"

                    previous_status = import_job.status
                    previous_processed = import_job.processed_rows

                # Stop streaming if job completed or failed
                if import_job.status in ['completed', 'failed']:
                    # Send final event
                    yield f"event: done\ndata: {{\"status\": \"{import_job.status}\"}}\n\n"
                    break

                # Wait before next check (poll every 1 second)
                await asyncio.sleep(1)

        except Exception as e:
            # Send error event
            yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"

        finally:
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

    return result
