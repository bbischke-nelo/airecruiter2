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
      // Redirect to SSO login
      if (typeof window !== 'undefined') {
        // Use the API login endpoint which handles SSO redirect
        window.location.href = '/recruiter2/api/v1/auth/login';
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
