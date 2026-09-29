import { apiClient } from './client';
import type { AuthTokenResponse, CurrentUserResponse } from './types';

export async function login(username: string, password: string) {
  const form = new URLSearchParams();
  form.set('username', username);
  form.set('password', password);

  const { data } = await apiClient.post<AuthTokenResponse>('/api/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
  return data;
}

export async function register(username: string, password: string) {
  const { data } = await apiClient.post<{ status: string; message: string }>('/api/auth/register', {
    username,
    password
  });
  return data;
}

export async function fetchCurrentUser() {
  const { data } = await apiClient.get<CurrentUserResponse>('/api/users/me');
  return data;
}
