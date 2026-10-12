import { apiClient } from './client';
import type { CareerCatalog } from './types';

let catalogRequest: Promise<CareerCatalog> | null = null;

export async function fetchCareerCatalog() {
  if (catalogRequest) return catalogRequest;
  catalogRequest = apiClient.get<CareerCatalog>('/api/career/catalog')
    .then(({ data }) => data)
    .finally(() => { catalogRequest = null; });
  return catalogRequest;
}
