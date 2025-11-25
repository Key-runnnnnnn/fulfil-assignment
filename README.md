# Fulfil Product Management System

A full-stack application for managing products with CSV import functionality, webhooks, and real-time updates.

---

## 🌐 Live Demo (Render Deployment)

**Deployment Guide**: See [`RENDER_DEPLOYMENT_STEPS.md`](RENDER_DEPLOYMENT_STEPS.md) for detailed deployment instructions.

**Quick Deploy**: See [`QUICK_DEPLOY.md`](QUICK_DEPLOY.md) for copy-paste environment variables.

---

## 🚀 Quick Start Guide for Local Development

### Prerequisites

Before running this project, ensure you have the following installed on your system:

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- **Git**

### Setup Instructions

1. **Clone the Repository**

   ```bash
   git clone https://github.com/Key-runnnnnnn/fulfil-assignment
   cd fulfil-assignment
   ```

2. **Start All Services with Docker Compose**

   ```bash
   docker-compose up --build
   ```

   This single command will:

   - Build the backend and frontend Docker images
   - Start PostgreSQL database
   - Start RabbitMQ message broker
   - Start Celery worker for background tasks
   - Start the FastAPI backend server
   - Start the React frontend development server

3. **Wait for Services to Initialize**

   The first time you run this, it may take 2-3 minutes to:

   - Download base images
   - Install dependencies
   - Initialize the database

   Look for these messages to confirm services are ready:

   ```
   backend     | INFO:     Application startup complete.
   frontend    | VITE ready in XXX ms
   rabbitmq    | Server startup complete
   ```

4. **Access the Application**

   Once all services are running:

   - **Frontend UI**: http://localhost:5173
   - **Backend API**: http://localhost:8000
   - **API Documentation**: http://localhost:8000/docs (Interactive Swagger UI)
   - **RabbitMQ Management**: http://localhost:15672 (username: `guest`, password: `guest`)

### Testing the Application

#### 1. **Product Management**

- Navigate to http://localhost:5173
- Use the "Products" tab to:
  - View all products with pagination
  - Create new products
  - Edit existing products
  - Delete products
  - Search and filter products

#### 2. **CSV Import Feature**

- Click on the "Upload CSV" tab
- **Sample CSV files are provided in the repository:**
  - `backend/a.csv` - Example CSV with product data
  - Use these files to test the import functionality
- CSV format requires columns: `sku`, `name`, `description`, `price`, `is_active`
- Upload the CSV file and watch real-time progress updates as products are imported
- Background processing is handled by Celery workers

#### 3. **Webhook Configuration**

- Go to the "Webhooks" tab
- Create webhook endpoints for events:
  - `product_created`
  - `product_updated`
  - `product_deleted`
- Test webhooks using the "Test" button
- Use services like [webhook.site](https://webhook.site) to receive test notifications

#### 4. **API Testing**

- Visit http://localhost:8000/docs for interactive API documentation
- Test all endpoints directly from the Swagger UI
- View request/response schemas and examples

### Stopping the Application

To stop all services:

```bash
# Press Ctrl+C in the terminal, then:
docker-compose down
```

To stop and remove all data (including database):

```bash
docker-compose down -v
```

### Troubleshooting

**If services fail to start:**

1. Ensure ports 5173, 8000, 5432, 5672, and 15672 are not in use
2. Check Docker daemon is running: `docker ps`
3. View logs: `docker-compose logs <service-name>` (e.g., `docker-compose logs backend`)

**To restart a specific service:**

```bash
docker-compose restart <service-name>
```

**To rebuild after code changes:**

```bash
docker-compose up --build
```

### Project Structure Overview

```
fulfil/
├── backend/          # FastAPI application
│   ├── app/         # Main application code
│   │   ├── api/     # API endpoints
│   │   ├── tasks/   # Celery background tasks
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         # React application
│   ├── src/
│   │   ├── pages/   # Page components
│   │   ├── components/
│   │   └── services/
│   ├── Dockerfile
│   └── package.json
└── docker-compose.yml
```

---

## Tech Stack

### Backend

- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Relational database
- **SQLAlchemy** - ORM
- **RabbitMQ** - Message broker
- **Celery** - Distributed task queue
- **Pydantic** - Data validation

### Frontend

- **React** - UI library
- **Vite** - Build tool
- **TailwindCSS** - Styling
- **Axios** - HTTP client

## Features

- ✅ Product CRUD operations
- ✅ CSV bulk import with progress tracking
- ✅ Webhook notifications for events
- ✅ Search and filtering
- ✅ Pagination
- ✅ Real-time progress updates
- ✅ Responsive UI

---

## 🚀 Deployment

### Render (Production)

This project is configured for deployment on Render with:
- Backend API (FastAPI)
- Celery Worker (Background tasks)
- Frontend (React Static Site)
- CloudAMQP (RabbitMQ)
- Neon (PostgreSQL)

**📖 Deployment Guides:**
- **Step-by-Step**: [`RENDER_DEPLOYMENT_STEPS.md`](RENDER_DEPLOYMENT_STEPS.md) - Complete deployment walkthrough
- **Quick Reference**: [`QUICK_DEPLOY.md`](QUICK_DEPLOY.md) - Environment variables and quick commands
- **CloudAMQP Setup**: [`CLOUDAMQP_SETUP.md`](CLOUDAMQP_SETUP.md) - RabbitMQ configuration details

**Deployment Order:**
1. Backend API (Web Service)
2. Celery Worker (Background Worker)
3. Frontend (Static Site)

All services are deployed individually through the Render dashboard.
