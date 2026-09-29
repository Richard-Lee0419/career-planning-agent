import { apiClient } from './client';
import type { LearningPathResponse, RoadmapHistoryResponse } from './types';

export async function fetchRoadmapHistory() {
  const { data } = await apiClient.get<RoadmapHistoryResponse>('/api/history/roadmaps');
  return data;
}

export async function fetchRoadmapVersion(id: number) {
  const { data } = await apiClient.get<LearningPathResponse>(`/api/history/roadmaps/${id}`);
  return data;
}

export async function saveRoadmapProgress(id: number, completedTasks: string[]) {
  const { data } = await apiClient.put<{ completed_tasks: string[] }>(`/api/history/roadmaps/${id}/progress`, {
    completed_tasks: completedTasks
  });
  return data;
}
