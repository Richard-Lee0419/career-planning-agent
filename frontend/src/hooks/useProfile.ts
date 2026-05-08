import { useCallback, useEffect, useState } from 'react';
import { fetchProfile } from '../api/profile';
import { getErrorMessage } from '../api/client';
import type { UserProfile } from '../api/types';

export function useProfile(autoLoad = true) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProfile();
      setProfile(data);
      return data;
    } catch (requestError) {
      const message = getErrorMessage(requestError, '暂无画像数据');
      setError(message);
      setProfile(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (autoLoad) void reload();
  }, [autoLoad, reload]);

  return { profile, loading, error, reload, setProfile };
}
