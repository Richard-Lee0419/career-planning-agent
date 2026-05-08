import type { JobItem, UserProfile } from '../api/types';

export interface CareerRecommendation {
  title: string;
  match: number;
  subtitle: string;
  reason: string;
  fitReasons: string[];
  strengths: string[];
  gaps: string[];
  nextAction: string;
}

const careerBlueprints = [
  {
    title: '产品经理',
    keywords: ['产品', '用户', '需求', '沟通', '运营', '商业', '项目', '原型'],
    subtitle: '用户洞察 · 需求拆解 · 项目推进',
    gaps: ['补齐需求分析方法', '沉淀可展示的产品案例', '训练数据复盘表达']
  },
  {
    title: '前端工程师',
    keywords: ['前端', 'React', 'Vue', 'JavaScript', 'TypeScript', '网页', '工程', '交互'],
    subtitle: '工程实现 · 交互体验 · 前端架构',
    gaps: ['补齐工程化项目经验', '加强性能优化和组件设计', '准备可演示作品集']
  },
  {
    title: '数据分析师',
    keywords: ['数据', 'SQL', 'Python', '统计', '分析', '可视化', '指标', '建模'],
    subtitle: '指标体系 · 数据建模 · 业务判断',
    gaps: ['补齐 SQL 与统计基础', '建立业务指标拆解能力', '完成 1 个端到端分析项目']
  },
  {
    title: 'AI 应用工程师',
    keywords: ['AI', '人工智能', '机器学习', '模型', '算法', 'Python', '大模型', '智能'],
    subtitle: '模型应用 · 工程落地 · 场景验证',
    gaps: ['补齐模型调用和评测经验', '强化 Python 工程能力', '构建可上线的 AI 应用样例']
  },
  {
    title: '运营增长',
    keywords: ['运营', '内容', '增长', '活动', '用户', '社群', '转化', '传播'],
    subtitle: '用户增长 · 内容策略 · 数据复盘',
    gaps: ['建立增长指标体系', '补齐 A/B 测试与复盘方法', '积累渠道运营案例']
  },
  {
    title: '后端工程师',
    keywords: ['后端', 'Java', 'Spring', '数据库', '接口', '服务', '架构', '系统'],
    subtitle: '服务开发 · 数据建模 · 系统稳定性',
    gaps: ['补齐数据库和接口设计', '完成可部署后端项目', '训练系统设计表达']
  }
];

export function hasCareerProfile(profile?: UserProfile | null) {
  if (!profile) return false;
  return Boolean(
    profile.name ||
      profile.major ||
      profile.current_skills.length ||
      profile.target_roles.length ||
      profile.interests.length ||
      profile.internship_experience
  );
}

export function getPrimaryTargetRole(profile?: UserProfile | null, fallback = '产品经理') {
  return profile?.target_roles?.[0] || fallback;
}

export function getProfileStrengths(profile?: UserProfile | null) {
  const strengths = [
    ...(profile?.current_skills || []).slice(0, 3),
    ...(profile?.soft_skills || []).slice(0, 2),
    ...(profile?.certificates || []).slice(0, 1)
  ].filter(Boolean);

  if (strengths.length) return strengths;
  return ['学习意愿明确', '职业探索空间大', '可通过测评快速形成画像'];
}

export function getProfileGaps(profile?: UserProfile | null) {
  const gaps: string[] = [];
  if (!profile?.target_roles?.length) gaps.push('先明确 1 个主目标岗位');
  if (!profile?.current_skills?.length) gaps.push('补充当前已掌握技能');
  if (!profile?.internship_experience) gaps.push('沉淀项目或实习证据');
  if (!profile?.certificates?.length) gaps.push('补充能证明能力的证书或作品');
  return gaps.length ? gaps : ['把已有能力转化为岗位作品证据', '针对目标岗位补齐关键技能'];
}

export function getCareerRecommendations(profile?: UserProfile | null, jobs: JobItem[] = []) {
  const targetRoles = profile?.target_roles || [];
  const userSignals = [
    ...(profile?.current_skills || []),
    ...(profile?.interests || []),
    ...(profile?.soft_skills || []),
    ...(profile?.target_roles || []),
    profile?.major || '',
    profile?.internship_experience || ''
  ]
    .join(' ')
    .toLowerCase();

  const jobTitles = jobs.map((job) => job.title).join(' ').toLowerCase();
  const strengths = getProfileStrengths(profile);

  const scored = careerBlueprints.map((blueprint, index) => {
    const keywordHits = blueprint.keywords.filter((keyword) => userSignals.includes(keyword.toLowerCase())).length;
    const targetHit = targetRoles.some((role) => role.includes(blueprint.title) || blueprint.title.includes(role));
    const marketHit = jobTitles.includes(blueprint.title.toLowerCase());
    const base = 68 + keywordHits * 5 + (targetHit ? 12 : 0) + (marketHit ? 4 : 0) - index;
    const match = Math.max(62, Math.min(96, base));

    return {
      title: blueprint.title,
      match,
      subtitle: blueprint.subtitle,
      reason: targetHit
        ? '你已经把它列为目标方向，系统会优先围绕该方向拆解能力差距和学习路径。'
        : `你的兴趣、技能或经历与“${blueprint.subtitle}”存在交集，适合继续验证岗位匹配度。`,
      fitReasons: [
        strengths[0] ? `已有优势：${strengths[0]}` : '当前画像仍在建立，适合先做低成本探索',
        profile?.major ? `专业背景可迁移：${profile.major}` : '可以通过项目作品快速建立岗位证据',
        profile?.interests?.[0] ? `兴趣倾向相关：${profile.interests[0]}` : '后续可通过 AI 顾问继续澄清兴趣方向'
      ],
      strengths: strengths.slice(0, 3),
      gaps: blueprint.gaps,
      nextAction: `生成 ${blueprint.title} 未来 12 周能力提升计划`
    } satisfies CareerRecommendation;
  });

  return scored.sort((a, b) => b.match - a.match).slice(0, 3);
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
    '请基于以上信息生成职业画像、能力标签、目标岗位、兴趣倾向和竞争力评分。'
  ].join('\n');
}
