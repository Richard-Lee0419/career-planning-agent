import { apiClient } from './client';
import type { JobsResponse, JobStatsResponse } from './types';

let statsRequest: Promise<JobStatsResponse> | null = null;

export async function fetchJobs(limit = 8, keyword?: string, location?: string) {
  const { data } = await apiClient.get<JobsResponse>('/api/jobs/search', {
    params: { limit, keyword, location }
  });
  return data;
}

export async function fetchJobStats() {
  if (statsRequest) return statsRequest;
  statsRequest = apiClient.get<JobStatsResponse>('/api/jobs/stats')
    .then(({ data }) => data)
    .finally(() => { statsRequest = null; });
  return statsRequest;
}
