import { apiClient } from './client';
import type { ChatRequest, ChatResponse, ChatSessionDetail, ChatSessionItem, GapAnalysisResponse, LearningPathResponse } from './types';
import { useAuthStore } from '../store/authStore';

const pendingRoadmapKeys = new Map<string, string>();
const pendingRoadmaps = new Map<string, Promise<LearningPathResponse>>();

export async function sendAgentChat(payload: ChatRequest, signal?: AbortSignal) {
  const { data } = await apiClient.post<ChatResponse>('/api/agent/chat', payload, { signal, timeout: 150000 });
  return data;
}

export async function createChatSession(targetRole?: string, roadmapId?: number) {
  const { data } = await apiClient.post<ChatSessionItem>('/api/chat/sessions', {
    target_role: targetRole || null, roadmap_id: roadmapId || null
  });
  return data;
}

export async function fetchChatSessions() {
  const { data } = await apiClient.get<{ data: ChatSessionItem[] }>('/api/chat/sessions');
  return data.data;
}

export async function fetchChatSession(id: string) {
  const { data } = await apiClient.get<ChatSessionDetail>(`/api/chat/sessions/${encodeURIComponent(id)}`);
  return data;
}

export async function clearChatSession(id: string) {
  await apiClient.delete(`/api/chat/sessions/${encodeURIComponent(id)}`);
}

export async function fetchGapAnalysis(targetRole: string) {
  const { data } = await apiClient.post<GapAnalysisResponse>('/api/agent/gap-analysis', null, {
    params: { target_role: targetRole }, timeout: 200000
  });
  return data;
}

export async function fetchLearningPath(targetRole: string) {
  const role = targetRole.trim();
  const scope = `${useAuthStore.getState().token || ''}:${role}`;
  const inFlight = pendingRoadmaps.get(scope);
  if (inFlight) return inFlight;
  const key = pendingRoadmapKeys.get(scope) || crypto.randomUUID();
  pendingRoadmapKeys.set(scope, key);
  const request = apiClient.post<LearningPathResponse>('/api/agent/learning-path', null, {
    params: { target_role: role }, headers: { 'Idempotency-Key': key }, timeout: 200000
  }).then(({ data }) => {
    pendingRoadmapKeys.delete(scope);
    return data;
  }).finally(() => pendingRoadmaps.delete(scope));
  pendingRoadmaps.set(scope, request);
  return request;
}

export async function exportReport(targetRole: string, roadmapId?: number | null) {
  const { data, headers } = await apiClient.post<Blob>('/api/report/export', null, {
    params: { target_role: targetRole || undefined, roadmap_id: roadmapId || undefined },
    responseType: 'blob'
  });

  const disposition = headers['content-disposition'] as string | undefined;
  const matched = disposition?.match(/filename="?([^"]+)"?/);
  const filename = matched?.[1] || `Career_Report_${targetRole}.md`;

  return { blob: data, filename };
}
