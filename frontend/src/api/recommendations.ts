import { apiClient } from './client';
import type { RoleMatch } from './types';
import { useAuthStore } from '../store/authStore';

type RecommendationsResponse = { data: RoleMatch[]; scoring_method: string };
const recommendationRequests = new Map<string, Promise<RecommendationsResponse>>();

export async function fetchRecommendations(domain?: string) {
  const key = JSON.stringify([useAuthStore.getState().token || '', domain || '']);
  const inFlight = recommendationRequests.get(key);
  if (inFlight) return inFlight;
  const request = apiClient.get<RecommendationsResponse>('/api/recommendations', { params: { domain } })
    .then(({ data }) => data)
    .finally(() => recommendationRequests.delete(key));
  recommendationRequests.set(key, request);
  return request;
}
