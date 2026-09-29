export function compactNumber(value: number) {
  return new Intl.NumberFormat('zh-CN', { notation: 'compact' }).format(value);
}

export function pickFirstTarget(profileTarget?: string[], fallback = '前端工程师') {
  return profileTarget?.find(Boolean) || fallback;
}
