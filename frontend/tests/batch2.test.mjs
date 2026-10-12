import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import vm from 'node:vm';

const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = readFileSync(new URL('../src/utils/careerPlan.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const careerPlan = {};
vm.runInNewContext(compiled, { exports: careerPlan, require: () => ({}) });

test('recommendation cards use only server evidence scores and actual requirements', () => {
  const profile = { current_skills: ['React'], soft_skills: ['团队协作'], certificates: [],
    target_roles: ['前端工程师'], interests: ['设计'] };
  const match = { role_name: '前端开发工程师', score: 47, matched_skills: ['React'],
    missing_skills: ['TypeScript', 'Git'], matched_soft_skills: ['团队协作'], missing_soft_skills: [],
    target_preference: true, interest_relevant: false, evidence: '基于岗位标准' };
  const result = careerPlan.getCareerRecommendations(profile, [match]);
  assert.equal(result[0].match, 47);
  assert.deepEqual(Array.from(result[0].gaps), ['TypeScript', 'Git']);
  const insufficient = careerPlan.getCareerRecommendations(profile, [{ ...match, score: null }]);
  assert.equal(insufficient.length, 1);
  assert.equal(insufficient[0].match, null);
  assert.match(insufficient[0].subtitle, /暂不评分/);
  assert.equal(careerPlan.getCareerRecommendations(profile, []).length, 0);
  assert.equal(careerPlan.roleNamesMatch('前端开发工程师', '前端工程师'), true);
});

test('exploration never creates a cross-domain ranking or silently substitutes an unknown target', () => {
  const base = { matched_skills: [], missing_skills: ['文案撰写'], matched_soft_skills: [],
    missing_soft_skills: [], target_preference: false, interest_relevant: false, evidence: '参考', score: 10 };
  const matches = [{ ...base, role_name: 'Java后端开发', domain: 'technology', score: 95 },
    { ...base, role_name: '内容运营', domain: 'marketing_content', score: 40 },
    { ...base, role_name: '招聘助理', domain: 'human_resources', score: 80 }];
  assert.equal(careerPlan.getCareerRecommendations({ target_roles: [] }, matches).length, 0);
  assert.equal(careerPlan.getCareerRecommendations({ target_roles: ['古籍修复'] }, matches).length, 0);
  const inferred = careerPlan.getCareerRecommendations({ target_roles: ['内容运营'] }, matches);
  assert.deepEqual(Array.from(inferred, (item) => item.title), ['内容运营']);
  const explicit = careerPlan.getCareerRecommendations({ target_roles: ['内容运营'] }, matches, 'human_resources');
  assert.deepEqual(Array.from(explicit, (item) => item.title), ['招聘助理']);
});

test('insufficient or changed standards keep their actual provenance instead of becoming a zero-score recommendation', () => {
  const standardSource = { type: 'manual_pilot', review_status: 'modified_unverified', version: 'pilot-v1',
    region: '中国大陆', tasks: [], sources: [], limitations: ['内容修改后需要复核'] };
  const match = { role_name: '招聘助理', domain: 'human_resources', domain_label: '人力资源', score: null,
    matched_skills: [], missing_skills: [], matched_soft_skills: [], missing_soft_skills: [],
    target_preference: true, interest_relevant: false, evidence: '来源变更后未确认', standard_source: standardSource };
  const [result] = careerPlan.getCareerRecommendations({ target_roles: ['招聘助理'] }, [match]);
  assert.equal(result.match, null);
  assert.equal(result.reason, '来源变更后未确认');
  assert.equal(result.standardSource, standardSource);
});

test('the selected target stays visible even when its score is lower than three alternatives', () => {
  const base = { domain: 'technology', matched_skills: [], missing_skills: [], matched_soft_skills: [],
    missing_soft_skills: [], target_preference: false, interest_relevant: false, evidence: '参考' };
  const matches = ['Java后端开发', '数据分析师', '软件测试工程师', '前端开发工程师']
    .map((role_name, index) => ({ ...base, role_name, score: 90 - index * 20 }));
  const result = careerPlan.getCareerRecommendations({ target_roles: ['前端工程师'] }, matches);
  assert.equal(result[0].title, '前端开发工程师');
  assert.equal(result[0].match, 30);
  assert.equal(result.length, 3);
});

test('assessment text keeps interests, soft skills and weekly learning time distinct', () => {
  const text = careerPlan.buildAssessmentProfileText({ interests: ['交互设计'], softSkills: ['沟通协调', '细致负责', '保密意识'],
    skills: ['React'], weeklyTime: '每周 6-10 小时', targetRoles: ['前端工程师'] });
  assert.match(text, /兴趣方向：交互设计/);
  assert.match(text, /软素质：沟通协调、细致负责、保密意识/);
  assert.match(text, /学习投入：每周 6-10 小时/);
});
