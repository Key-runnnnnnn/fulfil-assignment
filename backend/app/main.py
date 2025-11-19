from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api import products, webhooks
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Product Importer API for bulk CSV uploads with async processing",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "products",
            "description": "Product CRUD operations with filtering and pagination"
        },
        {
            "name": "webhooks",
            "description": "Webhook configuration and management for event notifications"
        },
        {
            "name": "health",
            "description": "Health check and system status"
        }
    ]
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    products.router,
    prefix=f"{settings.API_V1_PREFIX}/products",
    tags=["products"]
)

app.include_router(
    webhooks.router,
    prefix=f"{settings.API_V1_PREFIX}/webhooks",
    tags=["webhooks"]
)


@app.get("/", tags=["health"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Product Importer API",
        "version": "0.2.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "0.2.0"
    }


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info(f"{settings.APP_NAME} started successfully")
    # Initialize database tables (if database is available)
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
        logger.warning(
            "App will run without database connection. Please configure DATABASE_URL in .env")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info(f"{settings.APP_NAME} shutting down")
