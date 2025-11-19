import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Products API
export const productsAPI = {
  getAll: (params = {}) => {
    const { page = 1, pageSize = 20, sku, name, isActive, keyword } = params;
    return api.get('/products', {
      params: {
        page,
        page_size: pageSize,
        sku,
        name,
        is_active: isActive,
        keyword
      }
    });
  },

  getById: (id) => api.get(`/products/${id}`),

  create: (data) => api.post('/products/', data),

  update: (id, data) => api.put(`/products/${id}`, data),

  delete: (id) => api.delete(`/products/${id}`),

  bulkDelete: (ids) => api.delete('/products/', {
    params: { ids: ids.join(','), confirm: true }
  }),

  search: (keyword, limit = 20) =>
    api.get('/products/search/', { params: { q: keyword, limit } }),
};

// Webhooks API
export const webhooksAPI = {
  getAll: () => api.get('/webhooks/'),

  getById: (id) => api.get(`/webhooks/${id}`),

  create: (data) => api.post('/webhooks/', data),

  update: (id, data) => api.put(`/webhooks/${id}`, data),

  delete: (id) => api.delete(`/webhooks/${id}`),

  toggle: (id) => api.patch(`/webhooks/${id}/toggle`),

  test: (id) => api.post(`/webhooks/${id}/test`),

  getEventTypes: () => api.get('/webhooks/event-types'),
};

// Upload API
export const uploadAPI = {
  uploadCSV: (file, onProgress) => {
    const formData = new FormData();
    formData.append('file', file);

    return api.post('/upload/csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    });
  },

  getJobStatus: (jobId) => api.get(`/upload/jobs/${jobId}`),

  getAllJobs: () => api.get('/upload/jobs'),

  streamProgress: (jobId) => {
    return new EventSource(`${API_BASE_URL}/upload/progress/${jobId}`);
  },
};

export default api;
