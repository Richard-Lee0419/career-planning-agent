import { apiClient } from './client';
import type { ProfileExtractResponse, SyncProfileResponse, UserProfile } from './types';

export async function fetchProfile() {
  const { data } = await apiClient.get<UserProfile>('/api/profile/me');
  return data;
}

export async function extractProfileFromText(resumeText: string, sessionId?: string | null) {
  const { data } = await apiClient.post<ProfileExtractResponse>('/api/user/profile/extract', {
    session_id: sessionId,
    resume_text: resumeText
  });
  return data;
}

export async function uploadResume(file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<{ status: string; message: string; data: Record<string, unknown> }>(
    '/api/user/profile/upload-resume',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export async function syncProfileFromChat() {
  const { data } = await apiClient.post<SyncProfileResponse>('/api/user/profile/sync-from-chat');
  return data;
}
