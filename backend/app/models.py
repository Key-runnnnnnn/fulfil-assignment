from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Text, Index, func
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Product(Base):
    """
    Product model with case-insensitive SKU uniqueness.
    Supports CRUD operations and bulk CSV imports.
    """
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Case-insensitive unique index on SKU (PostgreSQL specific)
    __table_args__ = (
        Index('idx_sku_lower_unique', func.lower(sku), unique=True),
        Index('idx_sku', sku),
        Index('idx_name', name),
        Index('idx_is_active', is_active),
    )
    
    def __repr__(self):
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"


class Webhook(Base):
    """
    Webhook configuration model for event notifications.
    Supports multiple event types with custom headers.
    """
    __tablename__ = "webhooks"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(500), nullable=False)
    event_type = Column(String(50), nullable=False)  # 'import_complete', 'product_created', etc.
    is_enabled = Column(Boolean, default=True, nullable=False)
    headers = Column(Text, nullable=True)  # JSON string of custom headers
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Webhook(id={self.id}, url='{self.url}', event='{self.event_type}')>"


class ImportJob(Base):
    """
    Track CSV import job progress and status.
    Enables real-time progress monitoring via SSE.
    """
    __tablename__ = "import_jobs"
    
    id = Column(String(36), primary_key=True)  # UUID
    filename = Column(String(255), nullable=False)
    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ImportJob(id={self.id}, status='{self.status}', processed={self.processed_rows}/{self.total_rows})>"
