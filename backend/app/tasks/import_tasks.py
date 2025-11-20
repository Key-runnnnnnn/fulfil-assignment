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

CHUNK_SIZE = settings.CELERY_CHUNK_SIZE


@celery_app.task(bind=True, name='app.tasks.import_tasks.process_csv_import', max_retries=3)
def process_csv_import(self: Task, job_id: str, file_path: str):
    db = SessionLocal()

    try:
        logger.info(f"Starting CSV import for job_id: {job_id}")
        logger.info(f"File path: {file_path}")

        import_job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
        if not import_job:
            logger.error(f"Import job {job_id} not found")
            raise ValueError(f"Import job {job_id} not found")

        import_job.status = 'processing'
        db.commit()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        success_count = 0
        error_count = 0
        processed_rows = 0
        errors = []

        with open(file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)

            required_headers = {'sku', 'name', 'description'}
            optional_headers = {'price'}
            headers_lower = {h.lower().strip() for h in csv_reader.fieldnames}

            if not required_headers.issubset(headers_lower):
                missing = required_headers - headers_lower
                raise ValueError(
                    f"Missing required columns: {', '.join(missing)}")

            fieldnames = [h.lower().strip() for h in csv_reader.fieldnames]

            chunk = []

            for row_num, row in enumerate(csv_reader, start=2):
                normalized_row = {k.lower().strip(): v for k, v in row.items()}

                if not any(normalized_row.values()):
                    continue

                chunk.append((row_num, normalized_row))

                if len(chunk) >= CHUNK_SIZE:
                    chunk_success, chunk_errors = process_chunk(
                        db, chunk, import_job)
                    success_count += chunk_success
                    error_count += len(chunk_errors)
                    processed_rows += len(chunk)
                    errors.extend(chunk_errors)

                    update_job_progress(
                        db, import_job, processed_rows, success_count, error_count
                    )

                    chunk = []

            # Process remaining chunk
            if chunk:
                chunk_success, chunk_errors = process_chunk(
                    db, chunk, import_job)
                success_count += chunk_success
                error_count += len(chunk_errors)
                processed_rows += len(chunk)
                errors.extend(chunk_errors)

                update_job_progress(
                    db, import_job, processed_rows, success_count, error_count
                )

        import_job.status = 'completed'
        import_job.completed_at = datetime.utcnow()

        if errors:
            error_summary = f"Completed with {error_count} errors. First 10 errors:\n"
            error_summary += "\n".join(errors[:10])
            import_job.error_message = error_summary

        db.commit()

        logger.info(f"CSV import completed for job_id: {job_id}")
        logger.info(
            f"Total processed: {processed_rows}, Success: {success_count}, Errors: {error_count}")

        from app.tasks.webhook_tasks import trigger_webhooks_for_event
        trigger_webhooks_for_event.delay(  # type: ignore
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


def process_csv_import_sync(job_id: str, file_path: str):
    db = SessionLocal()

    try:
        logger.info(f"Starting synchronous CSV import for job_id: {job_id}")
        logger.info(f"File path: {file_path}")

        import_job = db.query(ImportJob).filter(ImportJob.id == job_id).first()
        if not import_job:
            logger.error(f"Import job {job_id} not found")
            raise ValueError(f"Import job {job_id} not found")

        import_job.status = 'processing'
        db.commit()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        success_count = 0
        error_count = 0
        processed_rows = 0
        errors = []

        with open(file_path, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)

            required_headers = {'sku', 'name', 'description'}
            headers_lower = {h.lower().strip() for h in csv_reader.fieldnames}

            if not required_headers.issubset(headers_lower):
                missing = required_headers - headers_lower
                raise ValueError(
                    f"Missing required columns: {', '.join(missing)}")

            chunk = []

            for row_num, row in enumerate(csv_reader, start=2):
                normalized_row = {k.lower().strip(): v for k, v in row.items()}

                if not any(normalized_row.values()):
                    continue

                chunk.append((row_num, normalized_row))

                if len(chunk) >= CHUNK_SIZE:
                    chunk_success, chunk_errors = process_chunk(
                        db, chunk, import_job)
                    success_count += chunk_success
                    error_count += len(chunk_errors)
                    processed_rows += len(chunk)
                    errors.extend(chunk_errors)

                    update_job_progress(
                        db, import_job, processed_rows, success_count, error_count
                    )

                    chunk = []

            # Process remaining chunk
            if chunk:
                chunk_success, chunk_errors = process_chunk(
                    db, chunk, import_job)
                success_count += chunk_success
                error_count += len(chunk_errors)
                processed_rows += len(chunk)
                errors.extend(chunk_errors)

                update_job_progress(
                    db, import_job, processed_rows, success_count, error_count
                )

        import_job.status = 'completed'
        import_job.completed_at = datetime.utcnow()

        if errors:
            error_summary = f"Completed with {error_count} errors. First 10 errors:\n"
            error_summary += "\n".join(errors[:10])
            import_job.error_message = error_summary

        db.commit()

        logger.info(f"Synchronous CSV import completed for job_id: {job_id}")
        logger.info(
            f"Total processed: {processed_rows}, Success: {success_count}, Errors: {error_count}")

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
    success_count = 0
    errors = []

    for row_num, row_dict in chunk:
        try:
            validated_row = validate_csv_row(row_dict)

            upsert_product(db, validated_row)
            success_count += 1

        except Exception as e:
            error_msg = f"Row {row_num}: {str(e)}"
            errors.append(error_msg)
            logger.warning(error_msg)

    return success_count, errors


def validate_csv_row(row_dict):
    try:
        if row_dict.get('price'):
            try:
                row_dict['price'] = Decimal(str(row_dict['price']))
            except (InvalidOperation, ValueError):
                raise ValueError(
                    f"Invalid price format: {row_dict.get('price')}")

        validated = CSVProductRow(**row_dict)
        return validated

    except Exception as e:
        raise ValueError(f"Validation error: {str(e)}")


def upsert_product(db, validated_row: CSVProductRow):
    sku_upper = validated_row.sku.upper()

    existing_product = db.query(Product).filter(
        func.lower(Product.sku) == sku_upper.lower()
    ).first()

    if existing_product:
        existing_product.name = validated_row.name
        existing_product.description = validated_row.description
        existing_product.price = validated_row.price
        existing_product.updated_at = datetime.utcnow()

        logger.debug(f"Updated product with SKU: {sku_upper}")

    else:
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

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Database integrity error: {str(e)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise ValueError(f"Database error: {str(e)}")


def update_job_progress(db, import_job: ImportJob, processed: int, success: int, errors: int):
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
