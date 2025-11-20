from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class ProductBase(BaseModel):
    sku: str = Field(..., max_length=100,
                     description="Unique product SKU (case-insensitive)")
    name: str = Field(..., max_length=255, description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    price: Optional[Decimal] = Field(
        None, ge=0, description="Product price (must be positive)")
    is_active: bool = Field(default=True, description="Active status")

    @field_validator('sku')
    @classmethod
    def sku_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('SKU cannot be empty or whitespace')
        return v.strip().upper()

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Product name cannot be empty')
        return v.strip()

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError('Price must be a positive number')
        return v


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('Product name cannot be empty')
        return v.strip() if v else None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int = Field(..., description="Total number of products")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


class WebhookBase(BaseModel):
    url: HttpUrl = Field(..., description="Webhook URL")
    event_type: str = Field(
        ...,
        pattern='^(import_complete|product_created|product_updated|product_deleted)$',
        description="Event type that triggers the webhook"
    )
    is_enabled: bool = Field(
        default=True, description="Webhook enabled status")
    headers: Optional[dict] = Field(
        None, description="Custom HTTP headers (JSON object)")

    @field_validator('event_type')
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        allowed = ['import_complete', 'product_created',
                   'product_updated', 'product_deleted']
        if v not in allowed:
            raise ValueError(
                f'Event type must be one of: {", ".join(allowed)}')
        return v


class WebhookCreate(WebhookBase):
    pass


class WebhookUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    event_type: Optional[str] = Field(
        None,
        pattern='^(import_complete|product_created|product_updated|product_deleted)$'
    )
    is_enabled: Optional[bool] = None
    headers: Optional[dict] = None


class WebhookResponse(BaseModel):
    id: int
    url: str
    event_type: str
    is_enabled: bool
    headers: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CSVProductRow(BaseModel):
    sku: str = Field(..., description="Product SKU from CSV")
    name: str = Field(..., description="Product name from CSV")
    description: Optional[str] = Field(
        None, description="Product description from CSV")
    price: Optional[Decimal] = Field(
        None, ge=0, description="Product price from CSV")

    @field_validator('sku', 'name')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip() if v else v


class UploadResponse(BaseModel):
    job_id: str = Field(..., description="Unique import job ID")
    task_id: str = Field(..., description="Celery task ID")
    filename: str = Field(..., description="Uploaded filename")
    message: str = Field(..., description="Status message")


class ImportJobStatus(BaseModel):
    job_id: str
    filename: str
    total_rows: int = Field(..., ge=0)
    processed_rows: int = Field(..., ge=0)
    success_count: int = Field(..., ge=0)
    error_count: int = Field(..., ge=0)
    status: str = Field(..., pattern='^(pending|processing|completed|failed)$')
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    progress_percentage: float = Field(..., ge=0,
                                       le=100, description="Progress as percentage")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = ['pending', 'processing', 'completed', 'failed']
        if v not in allowed:
            raise ValueError(f'Status must be one of: {", ".join(allowed)}')
        return v


class ProductFilterParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=100,
                           description="Items per page")
    sku: Optional[str] = Field(
        None, description="Filter by SKU (partial match)")
    name: Optional[str] = Field(
        None, description="Filter by name (partial match)")
    is_active: Optional[bool] = Field(
        None, description="Filter by active status")

    class Config:
        extra = 'forbid'


class BulkDeleteResponse(BaseModel):
    message: str
    count: int = Field(..., ge=0, description="Number of deleted products")


class WebhookTestResponse(BaseModel):
    message: str
    task_id: str
    webhook_url: str
