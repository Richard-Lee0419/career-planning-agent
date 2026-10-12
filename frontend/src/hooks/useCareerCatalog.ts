import { useCallback, useEffect, useState } from 'react';
import { fetchCareerCatalog } from '../api/catalog';
import { getErrorMessage } from '../api/client';
import type { CareerCatalog } from '../api/types';

export function useCareerCatalog() {
  const [catalog, setCatalog] = useState<CareerCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchCareerCatalog();
      setCatalog(response);
    } catch (requestError) {
      setCatalog(null);
      setError(getErrorMessage(requestError, '职业目录暂时无法加载'));
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void reload(); }, [reload]);
  return { catalog, loading, error, reload };
}
