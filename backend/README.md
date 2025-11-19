# Product Importer Backend

FastAPI backend for bulk CSV product imports with async processing.

## Features

- 🚀 FastAPI with async support
- 🗄️ PostgreSQL database with SQLAlchemy ORM
- 📦 Three core models: Product, Webhook, ImportJob
- 🔄 Database migrations with Alembic
- 🎯 Case-insensitive SKU uniqueness

## Setup

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your database credentials
```

### 4. Setup Database

Make sure PostgreSQL is running, then create the database:

```bash
# Using psql
psql -U postgres
CREATE DATABASE product_importer;
\q
```

### 5. Run Migrations

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial migration with Product, Webhook, ImportJob models"

# Apply migrations
alembic upgrade head
```

### 6. Run Application

```bash
uvicorn app.main:app --reload
```

### 7. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Database Models

### Product
- Case-insensitive unique SKU
- Supports active/inactive status
- Timestamps for created/updated

### Webhook
- Multiple event types support
- Custom headers configuration
- Enable/disable functionality

### ImportJob
- Track CSV import progress
- Real-time status updates
- Error tracking

## Project Structure

```
backend/
├── alembic/                  # Database migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── app/
│   ├── api/                  # API routes (to be added)
│   ├── tasks/                # Celery tasks (to be added)
│   ├── utils/                # Utilities (to be added)
│   ├── __init__.py
│   ├── config.py            # Configuration
│   ├── database.py          # Database connection
│   ├── main.py              # FastAPI app
│   └── models.py            # SQLAlchemy models
├── alembic.ini
├── requirements.txt
└── README.md
```

## Next Steps

1. ✅ Database models and configuration
2. ⏳ Add Pydantic schemas for validation
3. ⏳ Implement Product CRUD API
4. ⏳ Add webhook management
5. ⏳ Implement CSV upload with Celery
6. ⏳ Add real-time progress tracking (SSE)
