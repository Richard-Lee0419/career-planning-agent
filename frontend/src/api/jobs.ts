import { apiClient } from './client';
import type { JobsResponse, JobStatsResponse } from './types';

export async function fetchJobs(limit = 8, keyword?: string, location?: string) {
  const { data } = await apiClient.get<JobsResponse>('/api/jobs/search', {
    params: { limit, keyword, location }
  });
  return data;
}

export async function fetchJobStats() {
  const { data } = await apiClient.get<JobStatsResponse>('/api/jobs/stats');
  return data;
}
