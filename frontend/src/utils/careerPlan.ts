import type { CareerCatalogRole, RoleMatch, StandardSource, UserProfile } from '../api/types';

export interface CareerRecommendation {
  title: string;
  match: number | null;
  domain: string;
  domainLabel: string;
  standardSource?: StandardSource | null;
  subtitle: string;
  reason: string;
  fitReasons: string[];
  strengths: string[];
  gaps: string[];
  nextAction: string;
  evidence: string;
}

export function hasCareerProfile(profile?: UserProfile | null) {
  return Boolean(profile && (profile.name || profile.major || profile.current_skills.length ||
    profile.target_roles.length || profile.interests.length || profile.internship_experience));
}

export function getPrimaryTargetRole(profile?: UserProfile | null, fallback = '') {
  return profile?.target_roles?.[0] || fallback;
}

export function getProfileStrengths(profile?: UserProfile | null) {
  return [
    ...(profile?.current_skills || []).slice(0, 3),
    ...(profile?.soft_skills || []).slice(0, 2),
    ...(profile?.certificates || []).slice(0, 1)
  ].filter(Boolean);
}

export function getProfileGaps(profile?: UserProfile | null) {
  const gaps: string[] = [];
  if (!profile?.target_roles?.length) gaps.push('先明确 1 个主目标岗位');
  if (!profile?.current_skills?.length) gaps.push('补充当前已掌握技能');
  if (!profile?.internship_experience) gaps.push('补充项目或实习经历');
  return gaps;
}

export function roleNamesMatch(a: string, b: string) {
  const normalize = (value: string) => value.toLowerCase().replace(/开发/g, '').replace(/\s/g, '');
  return normalize(a) === normalize(b);
}

export function getTargetDomain(profile?: UserProfile | null, roles: Pick<CareerCatalogRole, 'role_name' | 'domain'>[] = []) {
  const target = getPrimaryTargetRole(profile);
  if (!target) return '';
  return roles.find((role) => roleNamesMatch(role.role_name, target))?.domain || '';
}

export function getCareerRecommendations(profile?: UserProfile | null, matches: RoleMatch[] = [], domain?: string) {
  const selectedDomain = domain || getTargetDomain(profile, matches.map((item) => ({
    role_name: item.role_name, domain: item.domain || 'technology'
  })));
  if (!selectedDomain) return [];
  const domainMatches = matches.filter((item) => (item.domain || 'technology') === selectedDomain);
  const target = domainMatches.find((item) => roleNamesMatch(item.role_name, getPrimaryTargetRole(profile)));
  const visibleMatches = target ? [target, ...domainMatches.filter((item) => item !== target)] : domainMatches;
  return visibleMatches.slice(0, 3).map((item) => {
    const fitReasons = [
      ...item.matched_skills.slice(0, 2).map((skill) => `已具备岗位要求：${skill}`),
      ...item.matched_soft_skills.slice(0, 1).map((skill) => `已具备软素质：${skill}`),
      ...(item.target_preference ? ['你已将该岗位列为目标方向'] : []),
      ...(item.interest_relevant ? ['你的兴趣与岗位描述有关'] : [])
    ];
    return {
      title: item.role_name,
      match: item.score,
      domain: item.domain || 'technology',
      domainLabel: item.domain_label || '技术与产品',
      standardSource: item.standard_source,
      subtitle: item.score === null ? '资料或标准依据不足，暂不评分' : '岗位标准覆盖参考',
      reason: item.score === null ? item.evidence : item.matched_skills.length
        ? `已覆盖 ${item.matched_skills.length} 项核心岗位要求；仍有 ${item.missing_skills.length} 项待补齐。`
        : `当前未找到已掌握技能与该岗位核心要求的直接匹配；请核对画像或探索能力差距。`,
      fitReasons: fitReasons.length ? fitReasons : ['目前没有直接匹配的证据'],
      strengths: [...item.matched_skills, ...item.matched_soft_skills].slice(0, 3),
      gaps: [...item.missing_skills, ...item.missing_soft_skills].slice(0, 3),
      nextAction: `探索 ${item.role_name} 学习路径`,
      evidence: item.evidence
    } satisfies CareerRecommendation;
  });
}

export function buildAssessmentProfileText(values: Record<string, unknown>) {
  const readList = (key: string) => {
    const value = values[key];
    if (Array.isArray(value)) return value.join('、');
    return String(value || '');
  };

  return [
    `姓名：${values.name || ''}`,
    `学历/年级：${values.education || ''} ${values.grade || ''}`,
    `专业：${values.major || ''}`,
    `所在城市：${values.location || ''}`,
    `兴趣方向：${readList('interests')}`,
    `当前技能：${readList('skills')}`,
    `软素质：${readList('softSkills')}`,
    `项目或实习经历：${values.experience || ''}`,
    `目标职业：${readList('targetRoles')}`,
    `学习投入：${values.weeklyTime || ''}`,
    `当前困惑：${values.concerns || ''}`,
    '请基于以上信息生成职业画像、能力标签、目标岗位和兴趣倾向。'
  ].join('\n');
}
