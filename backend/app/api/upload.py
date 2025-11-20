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

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = ['.csv']
UPLOAD_DIR = settings.UPLOAD_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)


def validate_csv_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed"
        )

    if file.content_type not in ['text/csv', 'application/vnd.ms-excel', 'application/csv']:
        raise HTTPException(
            status_code=400,
            detail="Invalid content type. Must be a CSV file"
        )


def count_csv_rows(content: bytes) -> int:
    try:
        text_content = content.decode('utf-8')
        csv_reader = csv.reader(io.StringIO(text_content))

        header = next(csv_reader, None)
        if not header:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        required_columns = ['sku', 'name', 'description']
        optional_columns = ['price']
        header_lower = [col.lower().strip() for col in header]

        for col in required_columns:
            if col not in header_lower:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required column: {col}. Required columns: {', '.join(required_columns)}. Optional: {', '.join(optional_columns)}"
                )

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
    validate_csv_file(file)

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)} MB"
        )

    total_rows = count_csv_rows(content)

    if total_rows == 0:
        raise HTTPException(
            status_code=400,
            detail="CSV file contains no data rows"
        )

    job_id = str(uuid.uuid4())

    file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(content)

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

    try:
        task = process_csv_import.delay(job_id, file_path)  # type: ignore
        task_id = task.id
    except Exception as e:
        logger.warning(
            f"Celery not available, processing synchronously: {str(e)}")
        try:
            from app.tasks.import_tasks import process_csv_import_sync
            process_csv_import_sync(job_id, file_path)
            task_id = "sync-execution"
        except Exception as sync_error:
            logger.error(f"Synchronous processing failed: {str(sync_error)}")
            import_job.status = 'failed'  # type: ignore
            import_job.error_message = str(sync_error)  # type: ignore
            db.commit()
            raise HTTPException(
                status_code=500, detail=f"Processing failed: {str(sync_error)}")

    return UploadResponse(
        job_id=job_id,
        task_id=task_id,
        filename=file.filename,  # type: ignore
        message=f"File uploaded successfully. Processing {total_rows} rows. Use job_id to track progress."
    )


@router.get("/status/{job_id}", response_model=ImportJobStatus)
async def get_import_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    import_job = db.query(ImportJob).filter(ImportJob.id == job_id).first()

    if not import_job:  # type: ignore
        raise HTTPException(status_code=404, detail="Import job not found")

    progress = 0.0
    if import_job.total_rows > 0:  # type: ignore
        progress = (import_job.processed_rows /
                    import_job.total_rows) * 100  # type: ignore

    return ImportJobStatus(  # type: ignore
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
    if limit > 100:
        limit = 100

    query = db.query(ImportJob)

    if status_filter:
        allowed_statuses = ['pending', 'processing', 'completed', 'failed']
        if status_filter not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}"
            )
        query = query.filter(ImportJob.status == status_filter)

    jobs = query.order_by(ImportJob.started_at.desc()).limit(limit).all()

    result = []
    for job in jobs:
        progress = 0.0
        if job.total_rows > 0:  # type: ignore
            progress = (job.processed_rows / job.total_rows) * \
                100  # type: ignore

        result.append(ImportJobStatus(  # type: ignore
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
    async def event_generator():
        db = SessionLocal()

        try:
            import_job = db.query(ImportJob).filter(
                ImportJob.id == job_id).first()

            if not import_job:
                yield f"event: error\ndata: {{\"error\": \"Import job not found\"}}\n\n"
                return

            previous_status = None
            previous_processed = -1

            while True:
                db.refresh(import_job)

                progress = 0.0
                if import_job.total_rows > 0:  # type: ignore
                    progress = (import_job.processed_rows /  # type: ignore
                                import_job.total_rows) * 100

                if (import_job.processed_rows != previous_processed or  # type: ignore
                        import_job.status != previous_status):  # type: ignore

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

                    if import_job.completed_at:  # type: ignore
                        progress_data["completed_at"] = import_job.completed_at.isoformat(  # type: ignore
                        )

                    if import_job.status == 'failed' and import_job.error_message:  # type: ignore
                        # type: ignore
                        progress_data["error_message"] = import_job.error_message

                    yield f"data: {json.dumps(progress_data)}\n\n"

                    previous_status = import_job.status
                    previous_processed = import_job.processed_rows

                if import_job.status in ['completed', 'failed']:
                    yield f"event: done\ndata: {{\"status\": \"{import_job.status}\"}}\n\n"
                    break

                await asyncio.sleep(1)

        except Exception as e:
            yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"

        finally:
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

    return result
