import { apiClient } from './client';
import type { RoleMatch } from './types';
import { useAuthStore } from '../store/authStore';

type RecommendationsResponse = { data: RoleMatch[]; scoring_method: string };
const recommendationRequests = new Map<string, Promise<RecommendationsResponse>>();

export async function fetchRecommendations() {
  const key = useAuthStore.getState().token || '';
  const inFlight = recommendationRequests.get(key);
  if (inFlight) return inFlight;
  const request = apiClient.get<RecommendationsResponse>('/api/recommendations')
    .then(({ data }) => data)
    .finally(() => recommendationRequests.delete(key));
  recommendationRequests.set(key, request);
  return request;
}
