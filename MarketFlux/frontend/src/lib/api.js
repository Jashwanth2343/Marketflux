import axios from 'axios';

const ENV_API_BASE = process.env.REACT_APP_BACKEND_URL?.trim();

if (process.env.NODE_ENV === 'production' && !ENV_API_BASE) {
  throw new Error(
    'REACT_APP_BACKEND_URL is required for a production build. ' +
    'Set it to the public API origin (for example https://marketflux-api.onrender.com) before running yarn build.'
  );
}

const API_BASE = (ENV_API_BASE || 'http://localhost:8000').replace(/\/$/, '');

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

export default api;
export { API_BASE };
