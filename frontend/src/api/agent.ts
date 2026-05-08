import { apiClient } from './client';
import type { ChatRequest, ChatResponse, GapAnalysisResponse, LearningPathResponse } from './types';

export async function sendAgentChat(payload: ChatRequest) {
  const { data } = await apiClient.post<ChatResponse>('/api/agent/chat', payload);
  return data;
}

export async function fetchGapAnalysis(targetRole: string) {
  const { data } = await apiClient.post<GapAnalysisResponse>('/api/agent/gap-analysis', null, {
    params: { target_role: targetRole }
  });
  return data;
}

export async function fetchLearningPath(targetRole: string) {
  const { data } = await apiClient.post<LearningPathResponse>('/api/agent/learning-path', null, {
    params: { target_role: targetRole }
  });
  return data;
}

export async function exportReport(targetRole: string) {
  const { data, headers } = await apiClient.post<Blob>('/api/report/export', null, {
    params: { target_role: targetRole },
    responseType: 'blob'
  });

  const disposition = headers['content-disposition'] as string | undefined;
  const matched = disposition?.match(/filename="?([^"]+)"?/);
  const filename = matched?.[1] || `Career_Report_${targetRole}.md`;

  return { blob: data, filename };
}
