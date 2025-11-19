"""
CSV Import Tasks
Handles asynchronous processing of CSV product imports with chunking and progress tracking.
"""
from celery import Task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ImportJob, Product
from app.schemas import CSVProductRow
from app.config import settings
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
import csv
import os

logger = logging.getLogger(__name__)

# Configuration from environment variables
CHUNK_SIZE = settings.CELERY_CHUNK_SIZE


@celery_app.task(bind=True, name='app.tasks.import_tasks.process_csv_import', max_retries=3)
def process_csv_import(self: Task, job_id: str, file_path: str):
    """
    Process CSV file import asynchronously with chunked processing.

    Args:
        job_id: Unique import job ID
        file_path: Path to uploaded CSV file

    This task:
    - Reads CSV file in chunks (1000 rows)
    - Validates each row using Pydantic schema
    - Upserts products (insert new, update existing by SKU)
    - Tracks progress in ImportJob table
    - Triggers webhooks on completion
    - Handles errors gracefully with detailed logging
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting CSV import for job_id: {job_id}")
        logger.info(f"File path: {file_path}")

        # Update job status to processing
        import_job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
        if not import_job:
            logger.error(f"Import job {job_id} not found")
            raise ValueError(f"Import job {job_id} not found")

        import_job.status = 'processing'
        db.commit()

        # Verify file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        # Process CSV file
        success_count = 0
        error_count = 0
        processed_rows = 0
        errors = []

        with open(file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)

            # Validate headers (price is optional)
            required_headers = {'sku', 'name', 'description'}
            optional_headers = {'price'}
            headers_lower = {h.lower().strip() for h in csv_reader.fieldnames}

            if not required_headers.issubset(headers_lower):
                missing = required_headers - headers_lower
                raise ValueError(
                    f"Missing required columns: {', '.join(missing)}")

            # Normalize headers to lowercase
            fieldnames = [h.lower().strip() for h in csv_reader.fieldnames]

            # Process in chunks
            chunk = []

            # Start at 2 (row 1 is header)
            for row_num, row in enumerate(csv_reader, start=2):
                # Normalize row keys
                normalized_row = {k.lower().strip(): v for k, v in row.items()}

                # Skip empty rows
                if not any(normalized_row.values()):
                    continue

                chunk.append((row_num, normalized_row))

                # Process chunk when it reaches CHUNK_SIZE
                if len(chunk) >= CHUNK_SIZE:
                    chunk_success, chunk_errors = process_chunk(
                        db, chunk, import_job)
                    success_count += chunk_success
                    error_count += len(chunk_errors)
                    processed_rows += len(chunk)
                    errors.extend(chunk_errors)

                    # Update progress
                    update_job_progress(
                        db, import_job, processed_rows, success_count, error_count
                    )

                    chunk = []  # Reset chunk

            # Process remaining rows in last chunk
            if chunk:
                chunk_success, chunk_errors = process_chunk(
                    db, chunk, import_job)
                success_count += chunk_success
                error_count += len(chunk_errors)
                processed_rows += len(chunk)
                errors.extend(chunk_errors)

                # Final progress update
                update_job_progress(
                    db, import_job, processed_rows, success_count, error_count
                )

        # Mark job as completed
        import_job.status = 'completed'
        import_job.completed_at = datetime.utcnow()

        # Store error summary if there were errors
        if errors:
            error_summary = f"Completed with {error_count} errors. First 10 errors:\n"
            error_summary += "\n".join(errors[:10])
            import_job.error_message = error_summary

        db.commit()

        logger.info(f"CSV import completed for job_id: {job_id}")
        logger.info(
            f"Total processed: {processed_rows}, Success: {success_count}, Errors: {error_count}")

        # Trigger webhooks for import_complete event
        from app.tasks.webhook_tasks import trigger_webhooks_for_event
        trigger_webhooks_for_event.delay(
            'import_complete',
            {
                'job_id': job_id,
                'filename': import_job.filename,
                'total_rows': import_job.total_rows,
                'processed_rows': processed_rows,
                'success_count': success_count,
                'error_count': error_count,
                'status': 'completed'
            }
        )

        # Clean up uploaded file
        try:
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}")

        return {
            'job_id': job_id,
            'status': 'completed',
            'processed_rows': processed_rows,
            'success_count': success_count,
            'error_count': error_count
        }

    except Exception as e:
        logger.error(
            f"CSV import failed for job_id: {job_id}: {str(e)}", exc_info=True)

        # Mark job as failed
        try:
            import_job = db.query(ImportJob).filter(
                ImportJob.id == job_id).first()
            if import_job:
                import_job.status = 'failed'
                import_job.error_message = str(e)
                import_job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")

        # Re-raise for Celery retry mechanism
        raise

    finally:
        db.close()


def process_csv_import_sync(job_id: str, file_path: str):
    """
    Process CSV file import synchronously (without Celery).

    This is a fallback function when RabbitMQ/Celery is not available.
    It performs the same operations as the async task but runs synchronously.

    Args:
        job_id: Unique import job ID
        file_path: Path to uploaded CSV file
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting synchronous CSV import for job_id: {job_id}")
        logger.info(f"File path: {file_path}")

        # Update job status to processing
        import_job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
        if not import_job:
            logger.error(f"Import job {job_id} not found")
            raise ValueError(f"Import job {job_id} not found")

        import_job.status = 'processing'
        db.commit()

        # Verify file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        # Process CSV file
        success_count = 0
        error_count = 0
        processed_rows = 0
        errors = []

        with open(file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)

            # Validate headers (price is optional)
            required_headers = {'sku', 'name', 'description'}
            headers_lower = {h.lower().strip() for h in csv_reader.fieldnames}

            if not required_headers.issubset(headers_lower):
                missing = required_headers - headers_lower
                raise ValueError(
                    f"Missing required columns: {', '.join(missing)}")

            # Process in chunks
            chunk = []

            # Start at 2 (row 1 is header)
            for row_num, row in enumerate(csv_reader, start=2):
                # Normalize row keys
                normalized_row = {k.lower().strip(): v for k, v in row.items()}

                # Skip empty rows
                if not any(normalized_row.values()):
                    continue

                chunk.append((row_num, normalized_row))

                # Process chunk when it reaches CHUNK_SIZE
                if len(chunk) >= CHUNK_SIZE:
                    chunk_success, chunk_errors = process_chunk(
                        db, chunk, import_job)
                    success_count += chunk_success
                    error_count += len(chunk_errors)
                    processed_rows += len(chunk)
                    errors.extend(chunk_errors)

                    # Update progress
                    update_job_progress(
                        db, import_job, processed_rows, success_count, error_count
                    )

                    chunk = []  # Reset chunk

            # Process remaining rows in last chunk
            if chunk:
                chunk_success, chunk_errors = process_chunk(
                    db, chunk, import_job)
                success_count += chunk_success
                error_count += len(chunk_errors)
                processed_rows += len(chunk)
                errors.extend(chunk_errors)

                # Final progress update
                update_job_progress(
                    db, import_job, processed_rows, success_count, error_count
                )

        # Mark job as completed
        import_job.status = 'completed'
        import_job.completed_at = datetime.utcnow()

        # Store error summary if there were errors
        if errors:
            error_summary = f"Completed with {error_count} errors. First 10 errors:\n"
            error_summary += "\n".join(errors[:10])
            import_job.error_message = error_summary

        db.commit()

        logger.info(f"Synchronous CSV import completed for job_id: {job_id}")
        logger.info(
            f"Total processed: {processed_rows}, Success: {success_count}, Errors: {error_count}")

        # Clean up uploaded file
        try:
            os.remove(file_path)
            logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}")

        return {
            'job_id': job_id,
            'status': 'completed',
            'processed_rows': processed_rows,
            'success_count': success_count,
            'error_count': error_count
        }

    except Exception as e:
        logger.error(
            f"Synchronous CSV import failed for job_id: {job_id}: {str(e)}", exc_info=True)

        # Mark job as failed
        try:
            import_job = db.query(ImportJob).filter(
                ImportJob.id == job_id).first()
            if import_job:
                import_job.status = 'failed'
                import_job.error_message = str(e)
                import_job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")

        raise

    finally:
        db.close()


def process_chunk(db, chunk, import_job):
    """
    Process a chunk of CSV rows.

    Args:
        db: Database session
        chunk: List of (row_num, row_dict) tuples
        import_job: ImportJob instance

    Returns:
        Tuple of (success_count, error_list)
    """
    success_count = 0
    errors = []

    for row_num, row_dict in chunk:
        try:
            # Validate row using Pydantic schema
            validated_row = validate_csv_row(row_dict)

            # Upsert product
            upsert_product(db, validated_row)
            success_count += 1

        except Exception as e:
            error_msg = f"Row {row_num}: {str(e)}"
            errors.append(error_msg)
            logger.warning(error_msg)

    return success_count, errors


def validate_csv_row(row_dict):
    """
    Validate a CSV row using Pydantic schema.

    Args:
        row_dict: Dictionary of row data

    Returns:
        Validated CSVProductRow instance

    Raises:
        ValueError: If validation fails
    """
    try:
        # Convert price to Decimal if present
        if row_dict.get('price'):
            try:
                row_dict['price'] = Decimal(str(row_dict['price']))
            except (InvalidOperation, ValueError):
                raise ValueError(
                    f"Invalid price format: {row_dict.get('price')}")

        # Validate using Pydantic
        validated = CSVProductRow(**row_dict)
        return validated

    except Exception as e:
        raise ValueError(f"Validation error: {str(e)}")


def upsert_product(db, validated_row: CSVProductRow):
    """
    Insert or update product based on SKU (case-insensitive).

    Args:
        db: Database session
        validated_row: Validated CSVProductRow instance
    """
    sku_upper = validated_row.sku.upper()

    # Check if product exists (case-insensitive)
    existing_product = db.query(Product).filter(
        func.lower(Product.sku) == sku_upper.lower()
    ).first()

    if existing_product:
        # Update existing product
        existing_product.name = validated_row.name
        existing_product.description = validated_row.description
        existing_product.price = validated_row.price
        existing_product.updated_at = datetime.utcnow()

        logger.debug(f"Updated product with SKU: {sku_upper}")

    else:
        # Insert new product
        new_product = Product(
            sku=sku_upper,
            name=validated_row.name,
            description=validated_row.description,
            price=validated_row.price,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_product)

        logger.debug(f"Inserted new product with SKU: {sku_upper}")

    # Commit each product individually for better error isolation
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise ValueError(f"Database error: {str(e)}")


def update_job_progress(db, import_job: ImportJob, processed: int, success: int, errors: int):
    """
    Update import job progress in database.

    Args:
        db: Database session
        import_job: ImportJob instance
        processed: Number of rows processed
        success: Number of successful imports
        errors: Number of errors
    """
    try:
        import_job.processed_rows = processed
        import_job.success_count = success
        import_job.error_count = errors
        db.commit()

        logger.info(
            f"Progress update - Job: {import_job.id}, Processed: {processed}/{import_job.total_rows}, Success: {success}, Errors: {errors}")

    except Exception as e:
        logger.error(f"Failed to update job progress: {e}")
        db.rollback()
