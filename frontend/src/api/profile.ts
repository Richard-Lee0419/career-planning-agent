import { apiClient } from './client';
import type { ProfileExtractResponse, SyncProfileResponse, UserProfile } from './types';
import { useAuthStore } from '../store/authStore';

const profileRequests = new Map<string, Promise<UserProfile>>();

export async function fetchProfile() {
  const key = useAuthStore.getState().token || '';
  const inFlight = profileRequests.get(key);
  if (inFlight) return inFlight;
  const request = apiClient.get<UserProfile>('/api/profile/me')
    .then(({ data }) => data)
    .finally(() => profileRequests.delete(key));
  profileRequests.set(key, request);
  return request;
}

export async function extractProfileFromText(resumeText: string, sessionId?: string | null, assessment?: Partial<UserProfile>) {
  const { data } = await apiClient.post<ProfileExtractResponse>('/api/user/profile/extract', {
    session_id: sessionId,
    resume_text: resumeText,
    assessment
  }, { timeout: 150000 });
  return data;
}

export async function uploadResume(file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<{ status: string; message: string; data: Record<string, unknown> }>(
    '/api/user/profile/upload-resume',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 150000 }
  );
  return data;
}

export async function syncProfileFromChat() {
  const { data } = await apiClient.post<SyncProfileResponse>('/api/user/profile/sync-from-chat', null,
    { timeout: 150000 });
  return data;
}
