# Product Importer - Frontend

A modern, responsive React application for managing product imports, inventory, and webhook notifications.

## 🚀 Features

### 1. CSV Product Import

- Drag & drop or browse to upload CSV files
- Real-time progress tracking with Server-Sent Events (SSE)
- Live statistics (total rows, processed, failed)
- Import history with status tracking
- Support for large files (up to 100MB)

### 2. Product Management

- View all products with pagination
- Search products by keyword
- Filter by SKU, name, or status
- Create, edit, and delete products
- Bulk delete functionality
- Inline status management

### 3. Webhook Configuration

- Create and manage webhooks for events
- Toggle webhook status (active/inactive)
- Test webhooks with sample payloads
- Custom headers support
- Available events:
  - `import.completed` - CSV import successful
  - `import.failed` - CSV import failed
  - `product.created` - New product added
  - `product.updated` - Product modified
  - `product.deleted` - Product removed

## 🛠 Tech Stack

- **React 19** - UI library
- **React Router 7** - Client-side routing
- **Tailwind CSS 4** - Utility-first styling
- **Vite 7** - Build tool and dev server
- **Axios** - HTTP client
- **Lucide React** - Icon library

## 📦 Installation

```bash
# Install dependencies
npm install

# Create environment file
cp .env.example .env

# Update API URL in .env
VITE_API_URL=http://localhost:8000/api/v1
```

## 🏃 Running the Application

### Development Mode

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Production Build

```bash
npm run build
npm run preview
```

## 📁 Project Structure

```
frontend/
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── UI.jsx         # Button, Input, Modal, etc.
│   │   └── Navbar.jsx     # Navigation bar
│   ├── pages/             # Route pages
│   │   ├── Upload.jsx     # CSV upload & progress
│   │   ├── Products.jsx   # Product management
│   │   └── Webhooks.jsx   # Webhook configuration
│   ├── services/          # API integration
│   │   └── api.js         # Axios API client
│   ├── App.jsx            # Main app with routing
│   ├── main.jsx           # Entry point
│   └── index.css          # Global styles
├── .env                   # Environment variables
├── .env.example           # Environment template
├── package.json           # Dependencies
└── vite.config.js         # Vite configuration
```

## 🎨 UI Components

### Reusable Components

- **Button** - Multiple variants (primary, secondary, danger, success, outline)
- **Card** - Container with shadow and border
- **Input** - Text input with label and error handling
- **Select** - Dropdown with options
- **Badge** - Status indicators
- **Modal** - Dialog overlay
- **Spinner** - Loading indicator
- **Alert** - Notification messages
- **ProgressBar** - Progress visualization
- **Table** - Data table with headers

## 🔌 API Integration

All API calls are centralized in `src/services/api.js`:

### Products API

```javascript
productsAPI.getAll({ page, pageSize, sku, name, isActive, keyword });
productsAPI.create(data);
productsAPI.update(id, data);
productsAPI.delete(id);
productsAPI.bulkDelete(ids);
productsAPI.search(keyword, limit);
```

### Webhooks API

```javascript
webhooksAPI.getAll();
webhooksAPI.create(data);
webhooksAPI.update(id, data);
webhooksAPI.delete(id);
webhooksAPI.toggle(id);
webhooksAPI.test(id);
webhooksAPI.getEventTypes();
```

### Upload API

```javascript
uploadAPI.uploadCSV(file, onProgress);
uploadAPI.getJobStatus(jobId);
uploadAPI.getAllJobs();
uploadAPI.streamProgress(jobId); // Returns EventSource
```

## 📊 Features in Detail

### Upload Page

- File validation (CSV only)
- Upload progress bar
- Real-time processing updates via SSE
- Processing statistics (total, processed, failed rows)
- Recent imports list with status
- CSV format requirements guide

### Products Page

- Paginated product list (20 per page)
- Real-time search with debouncing
- Advanced filters (SKU, name, status)
- Multi-select for bulk operations
- Create/Edit modal with form validation
- Status badges (Active/Inactive)
- Price formatting

### Webhooks Page

- Webhook list with status indicators
- Create/Edit modal with event type selection
- Custom headers management
- Toggle active/inactive status
- Test webhook functionality
- Event types documentation

## 🎯 User Experience

### Design Principles

- **Clean & Simple** - Minimalist interface, no clutter
- **Responsive** - Works on desktop, tablet, and mobile
- **Fast** - Optimized rendering and API calls
- **Intuitive** - Clear labels, helpful messages
- **Professional** - Consistent styling, smooth transitions

### Color Scheme

- **Primary**: Blue (#2563eb) - Actions, links, focus
- **Success**: Green (#16a34a) - Completed states
- **Warning**: Yellow (#ca8a04) - Pending states
- **Danger**: Red (#dc2626) - Errors, delete actions
- **Neutral**: Gray - Backgrounds, borders, text

## 📝 CSV Format

### Required Columns

- `name` - Product name (string)
- `sku` - Stock keeping unit (unique, string)
- `description` - Product description (string)

### Optional Columns

- `price` - Product price (decimal)

### Example

```csv
name,sku,description,price
Laptop,LAP-001,Dell Inspiron 15,799.99
Mouse,MOU-001,Wireless Mouse,29.99
Keyboard,KEY-001,Mechanical Keyboard,89.99
```

## 🌐 Deployment

### Vercel

```bash
npm run build
vercel --prod
```

### Netlify

```bash
npm run build
netlify deploy --prod --dir=dist
```

## 📄 License

MIT
