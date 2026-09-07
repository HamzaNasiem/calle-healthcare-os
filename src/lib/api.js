import axios from 'axios';

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

// Flag — ek hi baar refresh try karo, loop avoid karo
let isRefreshing = false;
let refreshQueue = [];

const processQueue = (error, token = null) => {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
  refreshQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retried &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      originalRequest._retried = true;
      isRefreshing = true;

      try {
        const refreshToken = getRefreshToken();
        if (!refreshToken) throw new Error('No refresh token');

        const refreshRes = await axios.post(
          `${API_URL}/auth/refresh`,
          { refresh_token: refreshToken }
        );
        const newToken = refreshRes.data?.token;
        const newRefreshToken = refreshRes.data?.refreshToken;

        if (newToken) {
          const usesLocal = !!localStorage.getItem('sb-token');
          const store = usesLocal ? localStorage : sessionStorage;
          store.setItem('sb-token', newToken);
          if (newRefreshToken) store.setItem('sb-refresh-token', newRefreshToken);
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          processQueue(null, newToken);
          return api(originalRequest);
        }
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearAuth();
        if (
          typeof window !== 'undefined' &&
          window.location.pathname !== '/login' &&
          window.location.pathname !== '/forgot-password'
        ) {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    if (status === 401) {
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        clearAuth();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
