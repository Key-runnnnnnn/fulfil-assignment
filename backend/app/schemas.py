from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class ProductBase(BaseModel):
    """Base product schema with common fields"""
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
        """Validate SKU is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError('SKU cannot be empty or whitespace')
        return v.strip().upper()  # Normalize to uppercase

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate name is not empty"""
        if not v or not v.strip():
            raise ValueError('Product name cannot be empty')
        return v.strip()

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure price is positive if provided"""
        if v is not None and v < 0:
            raise ValueError('Price must be a positive number')
        return v


class ProductCreate(ProductBase):
    """Schema for creating a new product"""
    pass


class ProductUpdate(BaseModel):
    """Schema for updating an existing product (all fields optional)"""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None

    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate name is not empty if provided"""
        if v is not None and not v.strip():
            raise ValueError('Product name cannot be empty')
        return v.strip() if v else None


class ProductResponse(ProductBase):
    """Schema for product API responses"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 


class ProductListResponse(BaseModel):
    """Schema for paginated product list responses"""
    items: List[ProductResponse]
    total: int = Field(..., description="Total number of products")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")



class WebhookBase(BaseModel):
    """Base webhook schema"""
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
        """Validate event type is one of the allowed values"""
        allowed = ['import_complete', 'product_created',
                   'product_updated', 'product_deleted']
        if v not in allowed:
            raise ValueError(
                f'Event type must be one of: {", ".join(allowed)}')
        return v


class WebhookCreate(WebhookBase):
    """Schema for creating a new webhook"""
    pass


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook (all fields optional)"""
    url: Optional[HttpUrl] = None
    event_type: Optional[str] = Field(
        None,
        pattern='^(import_complete|product_created|product_updated|product_deleted)$'
    )
    is_enabled: Optional[bool] = None
    headers: Optional[dict] = None


class WebhookResponse(BaseModel):
    """Schema for webhook API responses"""
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
    """Schema for validating individual CSV rows"""
    sku: str = Field(..., description="Product SKU from CSV")
    name: str = Field(..., description="Product name from CSV")
    description: Optional[str] = Field(
        None, description="Product description from CSV")
    price: Optional[Decimal] = Field(
        None, ge=0, description="Product price from CSV")

    @field_validator('sku', 'name')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip whitespace from string fields"""
        return v.strip() if v else v


class UploadResponse(BaseModel):
    """Schema for file upload response"""
    job_id: str = Field(..., description="Unique import job ID")
    task_id: str = Field(..., description="Celery task ID")
    filename: str = Field(..., description="Uploaded filename")
    message: str = Field(..., description="Status message")


class ImportJobStatus(BaseModel):
    """Schema for import job status response"""
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
        """Validate status is one of the allowed values"""
        allowed = ['pending', 'processing', 'completed', 'failed']
        if v not in allowed:
            raise ValueError(f'Status must be one of: {", ".join(allowed)}')
        return v


class ProductFilterParams(BaseModel):
    """Schema for product filtering and pagination parameters"""
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
    """Schema for bulk delete operation response"""
    message: str
    count: int = Field(..., ge=0, description="Number of deleted products")


class WebhookTestResponse(BaseModel):
    """Schema for webhook test response"""
    message: str
    task_id: str
    webhook_url: str
