import axios from 'axios';
import { handleMockRoute } from './mockFallback';

// Dynamically choose API based on environment, prioritizing VITE_API_URL
const API_URL = import.meta.env.VITE_API_URL || 
  (import.meta.env.PROD 
    ? 'https://calle-healthcare-os.onrender.com/api/v1' 
    : 'http://localhost:8000/api/v1');

export const getToken = () =>
  localStorage.getItem('sb-token') || sessionStorage.getItem('sb-token') || null;

export const getRefreshToken = () =>
  localStorage.getItem('sb-refresh-token') || sessionStorage.getItem('sb-refresh-token') || null;

export const getClinicInfo = () => {
  const raw = localStorage.getItem('clinic-info') || sessionStorage.getItem('clinic-info');
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const clearAuth = () => {
  ['sb-token', 'sb-refresh-token', 'clinic-info'].forEach((k) => {
    localStorage.removeItem(k);
    sessionStorage.removeItem(k);
  });
};

const api = axios.create({
  baseURL: API_URL,
  timeout: 45000, // 45s default to accommodate cloud cold starts
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
  },
});

api.interceptors.request.use(
  (config) => {
    // Auth login and wake-up routes get extra headroom for Render cold starts
    if (config.url && (config.url.includes('/auth/login') || config.url.includes('/ping') || config.url.includes('/health'))) {
      config.timeout = 75000;
    }
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status;
    if (status === 401) {
      clearAuth();
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
