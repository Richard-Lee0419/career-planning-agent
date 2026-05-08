import { apiClient } from './client';
import type { RoadmapHistoryResponse } from './types';

export async function fetchRoadmapHistory() {
  const { data } = await apiClient.get<RoadmapHistoryResponse>('/api/history/roadmaps');
  return data;
}
