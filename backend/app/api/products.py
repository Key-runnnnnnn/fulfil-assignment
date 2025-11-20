from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.database import get_db
from app.models import Product
from app.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
    BulkDeleteResponse
)
from typing import Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=ProductListResponse)
def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    sku: Optional[str] = Query(
        "", description="Filter by SKU (partial match, case-insensitive)"),
    name: Optional[str] = Query(
        "", description="Filter by name (partial match, case-insensitive)"),
    is_active: Optional[str] = Query(
        "", description="Filter by active status"),
    db: Session = Depends(get_db)
):
    query = db.query(Product)

    if sku and sku.strip():
        query = query.filter(func.lower(Product.sku).contains(sku.lower()))
    if name and name.strip():
        query = query.filter(func.lower(Product.name).contains(name.lower()))
    if is_active and is_active.strip():
        is_active_bool = is_active.lower() in ('true', '1', 'yes')
        query = query.filter(Product.is_active == is_active_bool)

    offset = (page - 1) * page_size
    products = query.order_by(Product.created_at.desc()).offset(
        offset).limit(page_size).all()

    if page == 1 and len(products) < page_size:
        total = len(products)
        total_pages = 1
    else:
        next_page_check = query.offset(offset + page_size).limit(1).first()
        if next_page_check:
            total = (page * page_size) + 100
            total_pages = page + 1
        else:
            total = (page - 1) * page_size + len(products)
            total_pages = page

    logger.info(
        f"Listed {len(products)} products (page {page}/{total_pages}, total: {total})")

    return ProductListResponse(  # type: ignore
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        logger.warning(f"Product not found: ID {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    logger.info(f"Retrieved product: {product.sku}")
    return product


@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(Product).filter(
        func.lower(Product.sku) == product.sku.lower()
    ).first()

    if existing:
        logger.warning(f"Duplicate SKU attempted: {product.sku}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{product.sku}' already exists"
        )

    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    logger.info(f"Created product: {db_product.sku} (ID: {db_product.id})")

    try:
        from app.tasks.webhook_tasks import trigger_webhooks_for_event
        trigger_webhooks_for_event.delay(  # type: ignore
            'product_created',
            {
                'product_id': db_product.id,
                'sku': db_product.sku,
                'name': db_product.name,
                'description': db_product.description,
                # type: ignore
                'price': str(db_product.price) if db_product.price else None,
                'is_active': db_product.is_active,
                'created_at': db_product.created_at.isoformat()
            }
        )
    except Exception as e:
        logger.warning(f"Failed to trigger product_created webhook: {e}")

    return db_product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product: ProductUpdate,
    db: Session = Depends(get_db)
):
    db_product = db.query(Product).filter(Product.id == product_id).first()

    if not db_product:
        logger.warning(f"Product not found for update: ID {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    update_data = product.model_dump(exclude_unset=True)

    if not update_data:
        logger.warning(f"No fields provided for update: ID {product_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update"
        )

    for field, value in update_data.items():
        setattr(db_product, field, value)

    db.commit()
    db.refresh(db_product)

    logger.info(f"Updated product: {db_product.sku} (ID: {product_id})")

    try:
        from app.tasks.webhook_tasks import trigger_webhooks_for_event
        trigger_webhooks_for_event.delay(  # type: ignore
            'product_updated',
            {
                'product_id': db_product.id,
                'sku': db_product.sku,
                'name': db_product.name,
                'description': db_product.description,
                # type: ignore
                'price': str(db_product.price) if db_product.price else None,
                'is_active': db_product.is_active,
                'updated_at': db_product.updated_at.isoformat(),
                'updated_fields': list(update_data.keys())
            }
        )
    except Exception as e:
        logger.warning(f"Failed to trigger product_updated webhook: {e}")

    return db_product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    db_product = db.query(Product).filter(Product.id == product_id).first()

    if not db_product:
        logger.warning(f"Product not found for deletion: ID {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    sku = db_product.sku
    product_data = {
        'product_id': db_product.id,
        'sku': db_product.sku,
        'name': db_product.name
    }

    db.delete(db_product)
    db.commit()

    logger.info(f"Deleted product: {sku} (ID: {product_id})")

    try:
        from app.tasks.webhook_tasks import trigger_webhooks_for_event
        trigger_webhooks_for_event.delay(  # type: ignore
            'product_deleted', product_data)
    except Exception as e:
        logger.warning(f"Failed to trigger product_deleted webhook: {e}")

    return None


@router.delete("/", response_model=BulkDeleteResponse)
def bulk_delete_products(
    confirm: bool = Query(
        False, description="Must be true to confirm bulk deletion"),
    db: Session = Depends(get_db)
):
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk delete requires explicit confirmation. Set confirm=true"
        )

    count = db.query(Product).count()

    if count == 0:
        logger.info("Bulk delete called but no products exist")
        return BulkDeleteResponse(
            message="No products to delete",
            count=0
        )

    db.query(Product).delete()
    db.commit()

    logger.warning(f"⚠️ BULK DELETE: Deleted all {count} products")

    try:
        from app.tasks.webhook_tasks import trigger_webhooks_for_event
        trigger_webhooks_for_event.delay(  # type: ignore
            'product_deleted',
            {
                'bulk_delete': True,
                'deleted_count': count,
                'message': 'All products deleted'
            }
        )
    except Exception as e:
        logger.warning(
            f"Failed to trigger product_deleted webhook for bulk delete: {e}")

    return BulkDeleteResponse(
        message=f"Successfully deleted all products",
        count=count
    )


@router.get("/search/", response_model=ProductListResponse)
def search_products(
    q: str = Query(..., min_length=1,
                   description="Search query (searches SKU, name, description)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    search_term = f"%{q.lower()}%"

    query = db.query(Product).filter(
        or_(
            func.lower(Product.sku).like(search_term),
            func.lower(Product.name).like(search_term),
            func.lower(Product.description).like(search_term)
        )
    )

    total = query.count()

    offset = (page - 1) * page_size
    products = query.order_by(Product.created_at.desc()).offset(
        offset).limit(page_size).all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    logger.info(f"Search '{q}' found {total} products")

    return ProductListResponse(  # type: ignore
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
