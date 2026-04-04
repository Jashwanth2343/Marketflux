import axios from 'axios';

const ENV_API_BASE = process.env.REACT_APP_BACKEND_URL?.trim();
const DEFAULT_API_BASE = 'http://localhost:8001';
const API_BASE = (ENV_API_BASE && ENV_API_BASE.length > 0 ? ENV_API_BASE : DEFAULT_API_BASE).replace(/\/$/, '');

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('mf_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
export { API_BASE };
