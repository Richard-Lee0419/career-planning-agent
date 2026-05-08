import axios, { AxiosError } from 'axios';
import { message } from 'antd';
import { useAuthStore } from '../store/authStore';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim();

export const apiClient = axios.create({
  baseURL: API_BASE_URL || undefined,
  timeout: 90000
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail || error.response?.data?.message;

    if (status === 401) {
      useAuthStore.getState().logout();
      message.warning('登录已过期，请重新登录');
    } else if (status && status >= 500) {
      message.error(detail || '服务暂时不可用');
    }

    return Promise.reject(error);
  }
);

export function getStaticAssetUrl(path?: string | null) {
  if (!path) return undefined;
  if (path.startsWith('http')) return path;
  return API_BASE_URL ? `${API_BASE_URL}${path}` : path;
}

export function getErrorMessage(error: unknown, fallback = '操作失败') {
  if (axios.isAxiosError<{ detail?: string; message?: string }>(error)) {
    return error.response?.data?.detail || error.response?.data?.message || fallback;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}
