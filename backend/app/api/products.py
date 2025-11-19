"""
Product CRUD API Endpoints
Handles all product operations: Create, Read, Update, Delete
"""

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
    sku: Optional[str] = Query("", description="Filter by SKU (partial match, case-insensitive)"),
    name: Optional[str] = Query("", description="Filter by name (partial match, case-insensitive)"),
    is_active: Optional[str] = Query("", description="Filter by active status"),
    db: Session = Depends(get_db)
):
    """
    List products with pagination and filtering.

    - **page**: Page number (default: 1)
    - **page_size**: Number of items per page (default: 50, max: 100)
    - **sku**: Filter by SKU (partial, case-insensitive)
    - **name**: Filter by product name (partial, case-insensitive)
    - **is_active**: Filter by active/inactive status
    """
    query = db.query(Product)

    # Apply filters (handle empty strings)
    if sku and sku.strip():
        query = query.filter(func.lower(Product.sku).contains(sku.lower()))
    if name and name.strip():
        query = query.filter(func.lower(Product.name).contains(name.lower()))
    if is_active and is_active.strip():
        # Convert string to boolean
        is_active_bool = is_active.lower() in ('true', '1', 'yes')
        query = query.filter(Product.is_active == is_active_bool)

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    products = query.order_by(Product.created_at.desc()).offset(
        offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    logger.info(
        f"Listed {len(products)} products (page {page}/{total_pages}, total: {total})")

    return ProductListResponse(
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
    """
    Get a single product by ID.

    - **product_id**: The ID of the product to retrieve
    """
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
    """
    Create a new product.

    - **sku**: Unique product SKU (case-insensitive, will be normalized to uppercase)
    - **name**: Product name (required)
    - **description**: Product description (optional)
    - **price**: Product price (optional, must be positive)
    - **is_active**: Active status (default: true)

    **Note:** SKU must be unique (case-insensitive). Duplicate SKUs will return 400 error.
    """
    # Check if SKU already exists (case-insensitive)
    existing = db.query(Product).filter(
        func.lower(Product.sku) == product.sku.lower()
    ).first()

    if existing:
        logger.warning(f"Duplicate SKU attempted: {product.sku}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product with SKU '{product.sku}' already exists"
        )

    # Create new product
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    logger.info(f"Created product: {db_product.sku} (ID: {db_product.id})")
    return db_product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    product: ProductUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing product.

    - **product_id**: The ID of the product to update
    - All fields are optional (only provided fields will be updated)

    **Note:** SKU cannot be changed after creation.
    """
    # Find existing product
    db_product = db.query(Product).filter(Product.id == product_id).first()

    if not db_product:
        logger.warning(f"Product not found for update: ID {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    # Update only provided fields
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
    return db_product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a single product by ID.

    - **product_id**: The ID of the product to delete
    """
    db_product = db.query(Product).filter(Product.id == product_id).first()

    if not db_product:
        logger.warning(f"Product not found for deletion: ID {product_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found"
        )

    sku = db_product.sku  # Store for logging
    db.delete(db_product)
    db.commit()

    logger.info(f"Deleted product: {sku} (ID: {product_id})")
    return None


@router.delete("/", response_model=BulkDeleteResponse)
def bulk_delete_products(
    confirm: bool = Query(
        False, description="Must be true to confirm bulk deletion"),
    db: Session = Depends(get_db)
):
    """
    Delete ALL products from the database (STORY 3).

    ⚠️ **WARNING**: This operation cannot be undone!

    - **confirm**: Must be set to `true` to proceed with deletion

    **Security**: Requires explicit confirmation via query parameter.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk delete requires explicit confirmation. Set confirm=true"
        )

    # Count products before deletion
    count = db.query(Product).count()

    if count == 0:
        logger.info("Bulk delete called but no products exist")
        return BulkDeleteResponse(
            message="No products to delete",
            count=0
        )

    # Delete all products
    db.query(Product).delete()
    db.commit()

    logger.warning(f"⚠️ BULK DELETE: Deleted all {count} products")

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
    """
    Search products across SKU, name, and description fields.

    - **q**: Search query string (minimum 1 character)
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    """
    search_term = f"%{q.lower()}%"

    query = db.query(Product).filter(
        or_(
            func.lower(Product.sku).like(search_term),
            func.lower(Product.name).like(search_term),
            func.lower(Product.description).like(search_term)
        )
    )

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    products = query.order_by(Product.created_at.desc()).offset(
        offset).limit(page_size).all()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    logger.info(f"Search '{q}' found {total} products")

    return ProductListResponse(
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )
