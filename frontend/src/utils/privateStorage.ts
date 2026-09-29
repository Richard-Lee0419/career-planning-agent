export function getUserStorageKey(base: string, userId?: number | null) {
  return typeof userId === 'number' && Number.isInteger(userId) && userId > 0
    ? `${base}:user:${userId}`
    : null;
}

export function clearLegacyPrivateStorage() {
  localStorage.removeItem('career-assessment-draft');
  localStorage.removeItem('career-roadmap-completed');
}
