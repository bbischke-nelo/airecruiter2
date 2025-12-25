import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Redirect to login page (which handles SSO redirect)
      if (typeof window !== 'undefined') {
        window.location.href = '/recruiter2/login';
      }
    }
    return Promise.reject(error);
  }
);

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  // Token is in HTTP-only cookie, so no manual header needed
  return config;
});
